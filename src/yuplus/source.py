"""Material capture. Fetching/parsing belongs to the Agent, never this module."""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from .core import YuError, canonical, digest, insert, new_id, now


_CHUNK = 1024 * 1024
_FEISHU_RESOURCE_ALIASES = {'docs': 'doc', 'sheets': 'sheet', 'base': 'bitable'}


def _io_error(exc: OSError, path: Path) -> YuError:
    code = 'FILE_NOT_FOUND' if isinstance(exc, FileNotFoundError) else 'DISK_FULL' if exc.errno == errno.ENOSPC else 'IO_FAILURE'
    return YuError(code, f'Cannot access material file: {path}', details=[{'path': str(path), 'reason': str(exc)}])


def _hash_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open('rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise YuError('INVALID_INPUT', 'Material assets must be regular files.')
        while chunk := source.read(_CHUNK):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _prepare_asset(data_dir: Path, asset: dict) -> dict:
    """Stream once to an immutable file, leaving at most an unreferenced blob."""
    path = Path(asset['local_path']).expanduser().resolve()
    staging_path = None
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise YuError('INVALID_INPUT', 'Material assets must be regular files.', details=[{'path': str(path)}])
        hasher = hashlib.sha256()
        size = 0
        output = None
        if asset['storage'] == 'copy':
            staging_dir = data_dir / 'staging'
            staging_dir.mkdir(parents=True, exist_ok=True)
            fd, filename = tempfile.mkstemp(prefix='capture-', dir=staging_dir)
            staging_path = Path(filename)
            output = os.fdopen(fd, 'wb')
        try:
            with path.open('rb') as source:
                before = os.fstat(source.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise YuError('INVALID_INPUT', 'Material assets must be regular files.')
                while chunk := source.read(_CHUNK):
                    hasher.update(chunk)
                    size += len(chunk)
                    if output is not None:
                        output.write(chunk)
                after = os.fstat(source.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise YuError('FILE_HASH_MISMATCH', 'Material changed while it was being captured.', details=[{'path': str(path)}])
            if output is not None:
                output.flush()
                os.fsync(output.fileno())
        finally:
            if output is not None:
                output.close()
        sha = hasher.hexdigest()
        expected = asset.get('expected_sha256')
        if expected and expected != sha:
            raise YuError('FILE_HASH_MISMATCH', 'Material bytes no longer match the requested digest.',
                          details=[{'path': str(path), 'expected': expected, 'actual': sha}])
        storage_key = f'sha256/{sha[:2]}/{sha}'
        if staging_path is not None:
            destination = data_dir / 'objects' / storage_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                # link() publishes without ever overwriting already-captured bytes.
                os.link(staging_path, destination)
                _fsync_directory(destination.parent)
            except FileExistsError:
                if _hash_file(destination) != (sha, size):
                    raise YuError('INTEGRITY_FAILURE', 'An existing object-store blob failed integrity verification.',
                                  details=[{'sha256': sha}])
        return {**asset, 'local_path': str(path), 'sha256': sha, 'size_bytes': size,
                'storage_key': storage_key}
    except OSError as exc:
        raise _io_error(exc, path) from exc
    finally:
        if staging_path is not None:
            staging_path.unlink(missing_ok=True)


def _message_identity(key, url, host, port):
    """Validate CLI chat/thread locators while identity remains scoped by IDs.

    CLI message links use chat positions or thread positions, not message IDs.
    Opaque share tokens cannot be checked against the chat scope: callers must
    use the verified chat AppLink fallback for those instead.
    """
    match = re.fullmatch(r'[A-Za-z0-9_-]+(?::[A-Za-z0-9_-]+)*:(oc_[A-Za-z0-9_-]+):(om_[A-Za-z0-9_-]+)', key)
    if not match or host not in {'applink.feishu.cn', 'applink.larksuite.com'} or port not in (None, 443):
        raise YuError('INVALID_INPUT', 'Message sources require a scoped identity and a trusted Feishu/Lark AppLink.')
    try:
        pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True, max_num_fields=10)
    except ValueError:
        raise YuError('INVALID_INPUT', 'Invalid message AppLink query.') from None
    query = dict(pairs)
    if len(query) != len(pairs):
        raise YuError('INVALID_INPUT', 'Message AppLink parameters must not be repeated.')
    chat_id = match[1]
    if url.path == '/client/chat/open':
        valid = (query.get('openChatId') == chat_id and set(query) <= {'openChatId', 'position'}
                 and ('position' not in query or re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', query['position'])))
    elif url.path == '/client/thread/open':
        chat_keys = {'openchatid', 'open_chat_id'} & query.keys()
        thread_keys = {'openthreadid', 'open_thread_id'} & query.keys()
        threads = {query[k] for k in thread_keys}
        valid = (bool(chat_keys) and bool(thread_keys) and len(threads) == 1
                 and all(query[k] == chat_id for k in chat_keys)
                 and re.fullmatch(r'(?:om|omt)_[A-Za-z0-9_-]+', next(iter(threads)))
                 and re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', query.get('thread_position', ''))
                 and set(query) <= {'openchatid', 'open_chat_id', 'openthreadid', 'open_thread_id', 'thread_position'})
    else:
        valid = False
    if not valid:
        raise YuError('INVALID_INPUT', 'Message AppLink must identify the scoped chat with supported position parameters.')
    return key, urlunsplit(('https', host, url.path, url.query, ''))


def _remote_identity(target: dict) -> tuple[str, str]:
    """Normalize supported public link forms without pretending to query Feishu."""
    try:
        url = urlsplit(target['canonical_url'])
    except ValueError:
        raise YuError('INVALID_INPUT', 'Invalid remote source URL.') from None
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise YuError('INVALID_INPUT', 'A remote source requires an HTTP(S) URL without credentials.')
    try:
        port = url.port
    except ValueError as exc:
        raise YuError('INVALID_INPUT', 'Invalid remote URL port.') from exc
    host = url.hostname.lower()
    authority = host + (f':{port}' if port and (url.scheme, port) not in (('http', 80), ('https', 443)) else '')
    path = url.path.rstrip('/') or '/'
    key = target['provider_key'].strip()
    if not key or any(c.isspace() for c in key):
        raise YuError('INVALID_INPUT', 'provider_key must be a stable resource identity.')
    if target['provider'] == 'feishu':
        if url.scheme != 'https' or not (host.endswith('.feishu.cn') or host.endswith('.larksuite.com') or host.endswith('.larkoffice.com')):
            raise YuError('INVALID_INPUT', 'Feishu sources require a supported HTTPS Feishu/Lark document link.')
        if target['resource_type'] == 'message':
            return _message_identity(key, url, host, port)
        match = re.fullmatch(r'/(docx|docs|doc|sheets|sheet|base|bitable|file|slides)/([A-Za-z0-9_-]+)', path)
        if not match:
            raise YuError('INVALID_INPUT', 'Resolve wiki/share links to the actual Feishu resource before import.')
        actual_type = _FEISHU_RESOURCE_ALIASES.get(match[1], match[1])
        supplied_type = _FEISHU_RESOURCE_ALIASES.get(target['resource_type'], target['resource_type'])
        if actual_type != supplied_type or '://' in key or key.split(':')[-1] != match[2]:
            raise YuError('INVALID_INPUT', 'Feishu provider_key/resource_type must identify the linked resource.')
        return key, urlunsplit(('https', authority, path, '', ''))
    # Query parameters can identify distinct web documents; only fragments are discarded.
    normalized_url = urlunsplit((url.scheme.lower(), authority, path, url.query, ''))
    return key, normalized_url


def prepare_import(data_dir: Path, request: dict) -> dict:
    """Called after receipt lookup, before BEGIN IMMEDIATE; never calls a model."""
    snapshot = request['snapshot']
    if snapshot['capture_scope']['kind'] == 'selection' and request['advance_head']:
        raise YuError('PARTIAL_CAPTURE_CANNOT_ADVANCE_HEAD', 'A selection cannot replace the whole-source head.')
    assets = snapshot.get('assets', [])
    if len({item['asset_id'] for item in assets}) != len(assets):
        raise YuError('INVALID_INPUT', 'Asset IDs must be unique within one snapshot.')
    target = request['target']
    identity = None
    if target['mode'] == 'create' and target['provider'] in ('feishu', 'web'):
        identity = _remote_identity(target)
    prepared_assets = [_prepare_asset(Path(data_dir), asset) for asset in assets]
    content = {'capture_scope': snapshot['capture_scope'], 'extraction_profile': snapshot['extraction_profile'],
               'body': snapshot.get('body'),
               'assets': [{'asset_id': a['asset_id'], 'role': a['role'], 'mime_type': a['mime_type'],
                           'sha256': a['sha256'], 'locator': a.get('locator', {})} for a in prepared_assets]}
    return {'assets': prepared_assets, 'content_hash': digest(content), 'remote_identity': identity}


def _get_source(db, project_id: str, source_id: str) -> dict:
    row = db.execute('SELECT * FROM sources WHERE project_id=? AND id=?', (project_id, source_id)).fetchone()
    if row is None:
        cross_project = db.execute('SELECT 1 FROM sources WHERE id=?', (source_id,)).fetchone()
        raise YuError('CROSS_PROJECT_REFERENCE' if cross_project else 'SOURCE_NOT_FOUND',
                      'The source does not belong to this project.', details=[{'source_id': source_id}])
    return dict(row)


def _duplicate_candidates(ctx, assets: list[dict]) -> list[dict]:
    original = [a for a in assets if a['role'] == 'original']
    wanted = sorted(a['sha256'] for a in original or assets)
    if not wanted:
        return []
    rows = ctx.db.execute('''SELECT s.id, s.cached_title, s.latest_snapshot_id,
        f.source_version_id, f.role, coalesce(f.blob_sha256,f.external_sha256) AS sha256
        FROM sources s JOIN source_versions v ON v.project_id=s.project_id AND v.source_id=s.id
        JOIN source_files f ON f.project_id=v.project_id AND f.source_version_id=v.id
        WHERE s.project_id=? AND s.provider='local' ''', (ctx.project_id,)).fetchall()
    grouped = {}
    for row in rows:
        grouped.setdefault(row['source_version_id'], []).append(row)
    result = {}
    for grouped_rows in grouped.values():
        originals = [r for r in grouped_rows if r['role'] == 'original']
        if sorted(r['sha256'] for r in originals or grouped_rows) == wanted:
            row = grouped_rows[0]
            result[row['id']] = {'source_id': row['id'], 'title': row['cached_title'],
                                 'head_snapshot_id': row['latest_snapshot_id']}
    return list(result.values())


def _assets_from_db(db, project_id: str, snapshot_id: str) -> list[dict]:
    rows = db.execute('''SELECT f.*, b.size_bytes, b.storage_key FROM source_files f
        LEFT JOIN blobs b ON f.blob_sha256=b.sha256
        WHERE f.project_id=? AND f.source_version_id=? ORDER BY f.rowid''', (project_id, snapshot_id)).fetchall()
    result = []
    for row in rows:
        copied = row['blob_sha256'] is not None
        item = {'asset_id': row['asset_id'], 'role': row['role'], 'display_name': row['display_name'],
                'mime_type': row['mime_type'], 'sha256': row['blob_sha256'] if copied else row['external_sha256'],
                'size_bytes': row['size_bytes'] if copied else row['external_size_bytes'],
                'storage': 'copy' if copied else 'external', 'locator': json.loads(row['original_locator_json'])}
        item['storage_key' if copied else 'local_path'] = row['storage_key'] if copied else row['external_path']
        result.append(item)
    return result


def _storage_manifest(assets: list[dict]) -> list[dict]:
    """Storage choices are snapshot metadata, independent of material content."""
    return [{'asset_id': asset['asset_id'], 'display_name': asset['display_name'],
             'storage': asset['storage'],
             'external_path': asset['local_path'] if asset['storage'] == 'external' else None}
            for asset in assets]


def import_source(ctx, request: dict, prepared: dict) -> dict:
    db, pid = ctx.db, ctx.project_id
    target, snapshot = request['target'], request['snapshot']
    if target['mode'] == 'create':
        provider = target['provider']
        resource_type = target['resource_type']
        if provider == 'feishu':
            resource_type = _FEISHU_RESOURCE_ALIASES.get(resource_type, resource_type)
        if provider in ('feishu', 'web'):
            key, url = prepared['remote_identity']
        else:
            key, url = target.get('provider_key') or new_id('identity'), target.get('canonical_url')
        existing = db.execute('''SELECT id,latest_snapshot_id FROM sources
            WHERE project_id=? AND provider=? AND resource_type=? AND provider_key=?''',
                              (pid, provider, resource_type, key)).fetchone()
        if existing:
            raise YuError('SOURCE_EXISTS', 'This source identity already exists; append using its current head.',
                          details=[{'source_id': existing['id'], 'head_snapshot_id': existing['latest_snapshot_id']}])
        if provider == 'local' and not target.get('provider_key'):
            candidates = _duplicate_candidates(ctx, prepared['assets'])
            if candidates:
                raise YuError('SOURCE_DUPLICATE', 'Identical local originals already exist. Reuse a source or give an explicit distinct provider_key.',
                              details=candidates)
        sid = new_id('src')
        insert(db, 'sources', project_id=pid, id=sid, provider=provider,
               resource_type=resource_type, provider_key=key, canonical_url=url,
               cached_title=snapshot['title'], created_at=now())
        source = _get_source(db, pid, sid)
    else:
        source = _get_source(db, pid, target['source_id'])
        sid = source['id']
        if source['archived_at'] is not None:
            raise YuError('INVALID_SCOPE', 'An archived source cannot receive new captures.')
        if target['base_snapshot_id'] != source['latest_snapshot_id']:
            raise YuError('BASE_REVISION_CONFLICT', 'The source head changed since it was read.',
                          details=[{'source_id': sid, 'expected': target['base_snapshot_id'],
                                    'actual': source['latest_snapshot_id']}])
    # Metadata and repeated-capture checks occur under the runner's write transaction.
    scope = canonical(snapshot['capture_scope'])
    params = [pid, sid, scope, snapshot['extraction_profile']]
    matching_sql = '''SELECT * FROM source_versions WHERE project_id=? AND source_id=?
                      AND capture_scope_json=? AND extraction_profile=?'''
    provider_revision = snapshot['provider_revision']
    if provider_revision is not None:
        matches = db.execute(matching_sql + ' AND provider_revision=? ORDER BY version DESC', params + [provider_revision]).fetchall()
        if any(row['content_hash'] != prepared['content_hash'] for row in matches):
            raise YuError('SOURCE_REVISION_CONFLICT', 'The same remote revision and extraction profile yielded different content.',
                          details=[{'source_id': sid, 'provider_revision': provider_revision}])
        reused = dict(matches[0]) if matches else None
    else:
        latest_match = db.execute(matching_sql + ' ORDER BY version DESC LIMIT 1', params).fetchone()
        reused = dict(latest_match) if latest_match and latest_match['content_hash'] == prepared['content_hash'] else None
        # Identical extracted content can belong to a later remote capture.
        # Keep the previous immutable baseline and record the new one separately.
        if reused and json.loads(reused['provenance_json']).get('remote_marker') != snapshot['provenance'].get('remote_marker'):
            reused = None
    before_head = source['latest_snapshot_id']
    if reused and request['advance_head'] and reused['id'] != before_head:
        raise YuError('SOURCE_REVISION_OUTDATED', 'A historical capture cannot replace the current source head.',
                      details=[{'snapshot_id': reused['id'], 'head_snapshot_id': before_head}])
    if reused and _storage_manifest(prepared['assets']) != _storage_manifest(_assets_from_db(db, pid, reused['id'])):
        # A request to keep a local copy or move an external original must not be
        # acknowledged as a no-op. Preserve the old evidence and append a local
        # snapshot, even when the material and remote revision are unchanged.
        reused = None
    metadata_changed = source['cached_title'] != snapshot['title']
    if metadata_changed:
        db.execute('UPDATE sources SET cached_title=? WHERE project_id=? AND id=?', (snapshot['title'], pid, sid))
    if reused:
        version_id, version = reused['id'], reused['version']
    else:
        version_id = new_id('sv')
        version = db.execute('SELECT coalesce(max(version),0)+1 FROM source_versions WHERE project_id=? AND source_id=?', (pid, sid)).fetchone()[0]
        body = snapshot.get('body')
        insert(db, 'source_versions', project_id=pid, id=version_id, source_id=sid, version=version,
               provider_revision=provider_revision, capture_scope_json=scope,
               extraction_profile=snapshot['extraction_profile'], content_hash=prepared['content_hash'],
               title_at_capture=snapshot['title'], body_text=body['text'] if body else None,
               body_format=body['format'] if body else None, provenance_json=canonical(snapshot['provenance']),
               captured_at=snapshot['captured_at'], recorded_at=now(), change_id=ctx.change_id)
        for asset in prepared['assets']:
            copied = asset['storage'] == 'copy'
            if copied:
                existing_blob = db.execute('SELECT size_bytes,storage_key FROM blobs WHERE sha256=?', (asset['sha256'],)).fetchone()
                if existing_blob and (existing_blob['size_bytes'] != asset['size_bytes'] or existing_blob['storage_key'] != asset['storage_key']):
                    raise YuError('INTEGRITY_FAILURE', 'Stored blob metadata disagrees with captured bytes.')
                if not existing_blob:
                    insert(db, 'blobs', sha256=asset['sha256'], size_bytes=asset['size_bytes'],
                           storage_key=asset['storage_key'], created_at=now())
            insert(db, 'source_files', project_id=pid, source_version_id=version_id,
                   asset_id=asset['asset_id'], role=asset['role'], display_name=asset['display_name'],
                   mime_type=asset['mime_type'], blob_sha256=asset['sha256'] if copied else None,
                   external_path=None if copied else asset['local_path'],
                   external_sha256=None if copied else asset['sha256'],
                   external_size_bytes=None if copied else asset['size_bytes'],
                   original_locator_json=canonical(asset.get('locator', {})))
        db.execute('UPDATE source_versions SET sealed=1 WHERE project_id=? AND id=?', (pid, version_id))
        if request['advance_head']:
            db.execute('UPDATE sources SET latest_snapshot_id=?,remote_observation_json=NULL,check_error_json=NULL,last_checked_at=NULL,observation_generation=observation_generation+1 WHERE project_id=? AND id=?', (version_id, pid, sid))
    head = version_id if not reused and request['advance_head'] else before_head
    effect = 'changed' if not reused or metadata_changed else 'noop'
    if effect == 'changed':
        ctx.changed_refs.append({'source_id': sid, 'snapshot_id': version_id, 'before_snapshot_id': before_head})
    dependents = db.execute('''SELECT DISTINCT o.id AS object_id, rs.item_id,
               rs.source_version_id AS adopted_source_version_id FROM revision_sources rs
        JOIN objects o ON o.project_id=rs.project_id AND o.current_revision_id=rs.revision_id
        JOIN source_versions sv ON sv.project_id=rs.project_id AND sv.id=rs.source_version_id
        WHERE o.project_id=? AND o.layer='draft' AND sv.source_id=? ORDER BY o.id,rs.item_id''', (pid, sid)).fetchall()
    return {'effect': effect, 'source_id': sid, 'snapshot_id': version_id, 'snapshot_version': version,
            'head_snapshot_id': head, 'snapshot_reused': reused is not None, 'title': snapshot['title'],
            'canonical_url': source['canonical_url'],
            'assets': [{k: asset[k] for k in ('asset_id', 'sha256', 'size_bytes', 'storage')}
                       for asset in _assets_from_db(db, pid, version_id)],
            'dependent_draft_items': [dict(row) for row in dependents]}


def show_source(db, pid: str, sid: str, snapshot_id: str | None = None, data_dir=None) -> dict:
    source = _get_source(db, pid, sid)
    selected = snapshot_id or source['latest_snapshot_id']
    result = {'source_id': sid, 'provider': source['provider'], 'resource_type': source['resource_type'],
              'provider_key': source['provider_key'], 'title': source['cached_title'],
              'canonical_url': source['canonical_url'], 'head_snapshot_id': source['latest_snapshot_id'], 'snapshot': None,
              'remote_observation': json.loads(source['remote_observation_json'] or 'null'),
              'check_error': json.loads(source['check_error_json'] or 'null'), 'last_checked_at':source['last_checked_at']}
    if selected is None:
        return result
    row = db.execute('SELECT * FROM source_versions WHERE project_id=? AND source_id=? AND id=?', (pid, sid, selected)).fetchone()
    if row is None:
        raise YuError('SOURCE_NOT_FOUND', 'The snapshot does not belong to the requested source.', details=[{'snapshot_id': selected}])
    assets = _assets_from_db(db, pid, selected)
    for asset in assets:
        if data_dir is not None:
            from .browser_view import asset_availability
            asset['availability']=asset_availability(data_dir,asset)
            continue
        if asset['storage'] == 'external':
            path = Path(asset['local_path'])
            try:
                if not path.is_file():
                    asset['availability'] = 'missing'
                elif _hash_file(path) == (asset['sha256'], asset['size_bytes']):
                    asset['availability'] = 'available'
                else:
                    asset['availability'] = 'changed'
            except OSError:
                asset['availability'] = 'unavailable'
    result['snapshot'] = {'snapshot_id': selected, 'snapshot_version': row['version'],
        'title': row['title_at_capture'], 'provider_revision': row['provider_revision'],
        'captured_at': row['captured_at'], 'recorded_at': row['recorded_at'],
        'capture_scope': json.loads(row['capture_scope_json']), 'extraction_profile': row['extraction_profile'],
        'provenance': json.loads(row['provenance_json']), 'content_hash': row['content_hash'],
        'body': {'format': row['body_format'], 'text': row['body_text']} if row['body_format'] else None, 'assets': assets}
    return result
