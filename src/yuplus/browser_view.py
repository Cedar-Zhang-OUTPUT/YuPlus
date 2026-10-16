"""Read-only presentation adapter; persisted identities and evidence remain authoritative."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from urllib.parse import urlencode

from .core import YuError, get_object, is_fresh, load_revision, now, selected_items
from .source import _assets_from_db


@contextmanager
def read_snapshot(data_dir):
    """One read-only connection and SQLite snapshot per request; never initialize here."""
    path = Path(data_dir).resolve() / 'yuplus.sqlite'
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        if db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise YuError('INTEGRITY_FAILURE', '数据库版本不兼容。')
        yield db
    finally:
        db.close()


def require_project(db, pid):
    if not pid or not db.execute('SELECT 1 FROM projects WHERE id=?', (pid,)).fetchone():
        raise YuError('PROJECT_NOT_FOUND', '项目不存在。')


def decoded(row):
    return {key.removesuffix('_json'): json.loads(value) if value is not None else None
            for key, value in dict(row).items() if key.endswith('_json')} | {
            key: value for key, value in dict(row).items() if not key.endswith('_json')}


def asset_path(data_dir, asset):
    if asset['storage'] == 'copy':
        root = Path(data_dir).resolve() / 'objects'
        expected = f"sha256/{asset['sha256'][:2]}/{asset['sha256']}"
        if asset['storage_key'] != expected:
            raise YuError('INTEGRITY_FAILURE', '资产存储位置无效。')
        path = root / expected
        # Reject symlink escape even if the target has identical bytes.
        if root.resolve() != root or not path.resolve().is_relative_to(root):
            raise YuError('INTEGRITY_FAILURE', '资产路径超出材料库。')
    else:
        path = Path(asset['local_path'])
        # Registration stores an absolute resolved path; a later symlink replacement is not it.
        if not path.is_absolute() or path.resolve() != path:
            raise YuError('INTEGRITY_FAILURE', '登记的资产路径已改变。')
    return path


def open_verified_asset(data_dir, asset):
    """Hash and stream the same descriptor, never a user-provided pathname."""
    path = asset_path(data_dir, asset)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    stream = os.fdopen(fd, 'rb')
    try:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise YuError('FILE_NOT_FOUND', '资产不是普通文件。')
        digest = hashlib.sha256()
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or before.st_size != asset['size_bytes'] or digest.hexdigest() != asset['sha256']:
            raise YuError('FILE_HASH_MISMATCH', '文件内容已变化，已保存版本的原字节不可用。')
        stream.seek(0)
        return stream, path
    except BaseException:
        stream.close()
        raise


def asset_availability(data_dir, asset):
    try:
        stream, _ = open_verified_asset(data_dir, asset)
        stream.close()
        return 'available'
    except FileNotFoundError:
        return 'missing'
    except YuError as exc:
        return 'changed' if exc.code == 'FILE_HASH_MISMATCH' else 'unavailable'
    except OSError:
        return 'unavailable'


def registered_asset(db, pid, version_id, asset_id):
    require_project(db, pid)
    for asset in _assets_from_db(db, pid, version_id):
        if asset['asset_id'] == asset_id:
            return asset
    raise YuError('FILE_NOT_FOUND', '该项目版本中未登记此资产。')


def basis_status(db, pid, dep):
    """Missing historical evidence is unknown; an actual removal at head is changed."""
    try:
        revision = load_revision(db, pid, dep['revision_id'])
        if revision['object_id'] != dep['object_id']:
            return 'unknown'
        selected_items(revision, dep['item_id'])
        obj = get_object(db, pid, dep['object_id'])
        if not obj['current_revision_id']:
            return 'unknown'
        load_revision(db, pid, obj['current_revision_id'])
        # Check historical and current dependency closure for missing evidence before
        # asking core freshness (which intentionally treats missing as simply stale).
        def evidence_exists(rid, item, seen):
            marker = (rid, item)
            if marker in seen:
                return False
            old = load_revision(db, pid, rid)
            entries = selected_items(old, item)
            producer = get_object(db, pid, old['object_id'])
            current = load_revision(db, pid, producer['current_revision_id'])
            try:
                current_entries = selected_items(current, item)
            except YuError as exc:
                if exc.code != 'INVALID_ITEM_REFERENCE':
                    raise
                current_entries = []  # An actually removed current item is changed.
            for rev, selected in ((old, entries), (current, current_entries)):
                for entry in selected:
                    ident = entry.get('item_id', entry.get('block_id'))
                    for child in rev['dependencies'].get(ident, []):
                        if not evidence_exists(child['revision_id'], child['item_id'], seen | {marker}):
                            return False
            return True
        if not evidence_exists(dep['revision_id'], dep['item_id'], set()):
            return 'unknown'
        # is_fresh follows transitive dependencies and fingerprints, not revision identity.
        return 'same' if is_fresh(db, pid, dep['revision_id'], dep['item_id']) else 'changed'
    except YuError:
        return 'unknown'


def browser_view(db, data_dir, project_id=None):
    catalog = json.loads((Path(__file__).parent / 'contracts/object-types.json').read_text())
    for obj in catalog['objects']:
        obj.update(meaning=obj['content_and_boundary'], boundary=obj['content_and_boundary'],
                   sources=obj['possible_sources'], usage=obj['downstream'], missing=obj['missing_policy'])
    arrays = ('objects', 'object_revisions', 'sources', 'source_versions', 'changes', 'decisions',
              'revision_sources', 'revision_dependencies', 'review_checks', 'exports', 'source_files', 'blobs')
    view = {key: [] for key in arrays}
    view.update(projects=[dict(row) for row in db.execute('SELECT * FROM projects ORDER BY created_at,id')],
                project_activity={}, catalog=catalog, basis_status_by_key={},
                meta={'demo': False, 'mode': 'live', 'data_dir': str(Path(data_dir).resolve()),
                      'project_id': project_id, 'generated_at': now()})
    for project in view['projects']:
        row = db.execute("SELECT id,reason,created_at FROM changes WHERE project_id=? AND effect='changed' ORDER BY seq DESC LIMIT 1", (project['id'],)).fetchone()
        view['project_activity'][project['id']] = {'change_id': row['id'], 'summary': row['reason'], 'at': row['created_at']} if row else None
    if not project_id:
        return view
    require_project(db, project_id)
    for table in arrays:
        if table in {'blobs', 'object_revisions', 'source_versions', 'source_files'}:
            continue
        view[table] = [decoded(row) for row in db.execute(f'SELECT * FROM {table} WHERE project_id=? ORDER BY rowid', (project_id,))]
    for change in view['changes']:
        change.pop('request_hash', None)
    for decision in view['decisions']:
        decision['instruction_source_version_id'] = decision['user_instruction_source_version_id']
    status = view['basis_status_by_key']
    def normalize_dep(dep):
        key = f"{dep['object_id']}:{dep['revision_id']}:{dep['item_id']}"
        if key not in status:
            status[key] = basis_status(db, project_id, dep)
        return {**dep, 'producer_object_id': dep['object_id'], 'producer_revision_id': dep['revision_id'],
                'producer_item_id': dep['item_id'], 'dependency_kind': dep['kind'], 'status': status[key]}
    for row in db.execute('SELECT id FROM object_revisions WHERE project_id=? AND sealed=1 ORDER BY rowid', (project_id,)):
        revision = load_revision(db, project_id, row['id'])
        revision.pop('payload_json'); revision.pop('block_lineage_json')
        revision['block_lineage'] = revision.pop('lineage')
        for entry in revision['payload'].get('items', revision['payload'].get('blocks', [])):
            ident = entry.get('item_id', entry.get('block_id'))
            entry['source_refs'] = [{**ref, 'evidence_kind': ref['kind']} for ref in revision['sources'].get(ident, [])]
            entry['dependencies'] = [normalize_dep(dep) for dep in revision['dependencies'].get(ident, [])]
        for lineage in revision['block_lineage'].values():
            lineage['basis'] = [normalize_dep(dep) for dep in lineage.get('basis', [])]
        view['object_revisions'].append(revision)
    for row in db.execute('SELECT * FROM source_versions WHERE project_id=? AND sealed=1 ORDER BY rowid', (project_id,)):
        version = decoded(row)
        scope = version['capture_scope']
        scope['mode'] = 'selection' if scope['kind'] == 'selection' else 'all'
        scope['note'] = scope.get('note') or (json.dumps(scope['locator'], ensure_ascii=False) if scope.get('locator') else '')
        version['assets'] = []
        for asset in _assets_from_db(db, project_id, version['id']):
            asset = dict(asset)
            asset['availability'] = asset_availability(data_dir, asset)
            asset['url'] = '/api/assets?' + urlencode({'project': project_id, 'version': version['id'], 'asset': asset['asset_id']})
            asset['source_version_id'] = version['id']
            version['assets'].append(asset)
            view['source_files'].append({**asset, 'project_id': project_id})
        view['source_versions'].append(version)
    return view
