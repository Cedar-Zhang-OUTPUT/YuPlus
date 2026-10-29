"""Explicit, planned hard deletion. Ordinary mutations remain append-only."""
from contextlib import contextmanager, nullcontext
import fcntl
import json
import re
import os
import tempfile
from pathlib import Path

from .core import YuError, canonical, digest, now

COMMANDS = {f'{kind}.purge' for kind in ('project', 'draft', 'review', 'source', 'library')}
KEYS = {'project': None, 'draft': 'object_id', 'review': 'object_id', 'source': 'source_id', 'library': 'library_id'}


def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS purge_requests (
      request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result_json TEXT NOT NULL,
      pending_json TEXT NOT NULL, created_at TEXT NOT NULL) STRICT''')
    db.execute('''CREATE TABLE IF NOT EXISTS purge_tombstones (
      identity TEXT PRIMARY KEY, kind TEXT NOT NULL, project_id TEXT,
      created_at TEXT NOT NULL) STRICT''')
    db.execute('''CREATE TABLE IF NOT EXISTS purged_requests (
      namespace TEXT NOT NULL, request_id TEXT NOT NULL, PRIMARY KEY(namespace,request_id)) STRICT''')
    db.execute('PRAGMA user_version=10')


@contextmanager
def storage_lock(app):
    """Serialize asset preparation through commit with purge's file cleanup."""
    directory = app.data_dir / 'locks'
    directory.mkdir(exist_ok=True)
    with (directory / 'storage.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise YuError('DATABASE_BUSY', '材料正在收录或清理，请稍后重试。') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def refers(value, identities):
    return any(s in identities or any(s.startswith(prefix + ident) for prefix in ('review:', 'proposal:') for ident in identities)
               or any(s.startswith(ident + ':') for ident in identities) for s in strings(value))


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def inventory(db):
    return {r[0]: [c[1] for c in db.execute(f'PRAGMA table_info({quoted(r[0])})')]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def plan(app, kind, pid, ident):
    db = app.db
    tables = inventory(db)
    chosen = {}

    def take(table, condition, values):
        if pid and 'project_id' in tables[table]:
            condition = '(' + condition + ') AND project_id=?'
            values = (*values, pid)
        rows = [dict(r) for r in db.execute(f'SELECT rowid AS _rowid,* FROM {quoted(table)} WHERE {condition}', values)]
        chosen.setdefault(table, {}).update({r['_rowid']: r for r in rows})
        return rows

    def take_ids(table, field, values):
        if not values:
            return []
        return take(table, f'{quoted(field)} IN ({",".join("?" for _ in values)})', tuple(values))

    if kind == 'library':
        roots = take('case_libraries', 'id=?', (ident,))
    elif kind == 'project':
        roots = take('projects', 'id=?', (ident,))
    else:
        app._project(pid)
        roots = take('sources' if kind == 'source' else 'objects', 'project_id=? AND id=?', (pid, ident))
    if not roots:
        raise YuError('TARGET_NOT_FOUND', '目标不存在或不属于当前项目。')
    if kind in ('draft', 'review') and roots[0]['layer'] != kind:
        raise YuError('INVALID_SCOPE', '对象层与命令不一致。')
    blockers = []
    schedules = []
    if kind == 'project':
        for table, columns in tables.items():
            if 'project_id' in columns and table not in ('purge_tombstones',):
                take(table, 'project_id=?', (pid,))
        monitors = [r['id'] for r in chosen.get('chat_monitors', {}).values()]
        runs = [r['id'] for r in chosen.get('monitor_runs', {}).values()]
        take_ids('monitor_messages', 'monitor_id', monitors)
        take_ids('monitor_steps', 'run_id', runs)
        for table in ('chat_monitors', 'collaboration_docs'):
            for row in chosen.get(table, {}).values():
                schedule = json.loads(row['schedule_json'])
                if schedule.get('automation_id'):
                    schedules.append({'kind': table, 'id': row.get('id', pid), 'schedule': schedule})
        for lease in chosen.get('monitor_leases', {}).values():
            if lease['expires_at'] > now():
                blockers.append({'table': 'monitor_leases', 'id': lease['run_id'], 'reason': '群同步仍持有有效执行租约，请等待完成或暂停后重试。'})
    elif kind == 'source':
        versions = take('source_versions', 'project_id=? AND source_id=?', (pid, ident))
        take_ids('source_files', 'source_version_id', [r['id'] for r in versions])
    elif kind in ('draft', 'review'):
        if kind == 'review':
            take('objects', "project_id=? AND type_key='expression_guide' AND scope_key=?", (pid, 'review:' + ident))
        versions = take_ids('object_revisions', 'object_id', [r['id'] for r in chosen['objects'].values()])
        revisions = [r['id'] for r in versions]
        take_ids('revision_sources', 'revision_id', revisions)
        take_ids('revision_dependencies', 'consumer_revision_id', revisions)
        take_ids('review_checks', 'review_revision_id', revisions)

    identities = {r['id'] for rows in chosen.values() for r in rows.values() if 'id' in r}
    # Check actual SQL references as well as JSON business relationships and receipts.
    # Histories count too: hiding a consumer cannot remove a provenance dependency.
    if kind != 'project':
        for table, columns in tables.items():
            if table in ('changes', 'case_library_requests', 'purge_requests', 'purge_tombstones', 'purged_requests', 'blobs', 'workspace_logo', 'logo_requests'):
                continue
            condition = ' WHERE project_id=?' if pid and 'project_id' in columns else ''
            for raw in db.execute(f'SELECT rowid AS _rowid,* FROM {quoted(table)}{condition}', (pid,) if condition else ()):
                row = dict(raw)
                if row['_rowid'] in chosen.get(table, {}):
                    continue
                values = {k: (json.loads(v) if k.endswith('_json') and v else v) for k, v in row.items()}
                if refers(values, identities):
                    blockers.append({'table': table, 'id': row.get('id', row.get('request_id', row.get('run_id'))),
                                     'reason': '仍有当前或历史记录引用此内容。'})

    assets = list(chosen.get('source_files', {}).values())
    removed_files = set(chosen.get('source_files', {}))
    remaining = [dict(r) for r in db.execute('SELECT rowid AS _rowid,* FROM source_files') if r['_rowid'] not in removed_files]
    used_blobs = {r['blob_sha256'] for r in remaining}
    used_external = {r['external_sha256'] for r in remaining}
    cleanup = []
    shared = set()
    for sha in {r['blob_sha256'] for r in assets if r['blob_sha256']}:
        if sha in used_blobs:
            shared.add(sha)
        else:
            cleanup.append({'kind': 'blob', 'sha256': sha, 'path': f'objects/sha256/{sha[:2]}/{sha}'})
    # Restored external copies are managed by Yu+. Original external files never are.
    for sha in {r['external_sha256'] for r in assets if r['external_sha256']} - used_external:
        path = f'external-files/{sha}'
        if (app.data_dir / path).exists():
            cleanup.append({'kind': 'restored', 'sha256': sha, 'path': path})
    if kind == 'project' and chosen.get('case_research'):
        from .case_preview import PreviewCache
        cache = PreviewCache(app.data_dir)
        for row in chosen['case_research'].values():
            if row['board_token']:
                prefix = cache.prefix(row)
                cleanup.append({'kind': 'preview', 'sha256': prefix, 'path': 'case-previews/' + prefix})
    count = {t: len(rows) for t, rows in chosen.items() if rows}
    redactions = {}
    for table in ('changes', 'case_library_requests'):
        for raw in db.execute(f'SELECT rowid AS _rowid,* FROM {table}'):
            row = dict(raw)
            if row['_rowid'] not in chosen.get(table, {}) and refers(json.loads(row['result_json']), identities):
                redactions.setdefault(table, []).append(row)
    fingerprint = digest({'kind': kind, 'project': pid, 'id': ident, 'rows': chosen,
                          'redactions': redactions, 'blockers': blockers,
                          'cleanup': sorted(cleanup, key=lambda x: x['path']), 'shared': sorted(shared)})
    result = {'deletion_mode': 'hard', 'dry_run': True, 'target_id': ident, 'project_id': pid,
              'target_name': roots[0].get('name', roots[0].get('cached_title', roots[0].get('type_key'))),
              'plan_hash': fingerprint, 'can_execute': not blockers, 'records': count,
              'history_receipts_redacted': {t: len(rows) for t, rows in redactions.items()},
              'requires_scheduler_handling': bool(schedules),
              'managed_files_to_delete': sum(f['kind'] != 'preview' for f in cleanup),
              'preview_caches_to_clear': sum(f['kind'] == 'preview' for f in cleanup),
              'shared_files_retained': len(shared),
              'blockers': blockers, 'scheduler_actions': schedules,
              'scope_note': '删除所列本地记录及其历史；不删除飞书内容、用户外部原件、已有备份。最小删除回执仍保留；不是磁盘取证级擦除。'}
    return result, chosen, cleanup, identities


def cleanup_files(app, request_id):
    """Durable retry after DB commit. Never remove a newly referenced blob."""
    db = app.db
    row = db.execute('SELECT * FROM purge_requests WHERE request_id=?', (request_id,)).fetchone()
    pending = json.loads(row['pending_json'])
    result = json.loads(row['result_json'])
    errors = []
    left = []
    for item in pending:
        sha, relative = item['sha256'], item['path']
        if item['kind'] == 'preview':
            if not re.fullmatch(r'[0-9a-f]{64}', sha) or relative != 'case-previews/' + sha:
                raise YuError('INTEGRITY_FAILURE', '预览缓存清理记录无效。')
            from .case_preview import PreviewCache
            try:
                cache = PreviewCache(app.data_dir)
                with cache.lock():
                    for path in cache.root.glob(sha + '*'):
                        if path.name == sha + '.json' or re.fullmatch(sha + r'_[a-f0-9]{64}', path.name):
                            path.unlink(missing_ok=True)
            except (OSError, YuError) as exc:
                left.append(item)
                errors.append({'file': relative, 'message': str(exc)})
            continue
        if not re.fullmatch(r'[0-9a-f]{64}', sha) or relative != (f'objects/sha256/{sha[:2]}/{sha}' if item['kind'] == 'blob' else f'external-files/{sha}'):
            raise YuError('INTEGRITY_FAILURE', '清理记录的文件路径无效。')
        field = 'blob_sha256' if item['kind'] == 'blob' else 'external_sha256'
        db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute(f'SELECT 1 FROM source_files WHERE {field}=?', (sha,)).fetchone():
                db.execute('COMMIT')
                continue
            path = app.data_dir / relative
            if path.is_symlink() or path.resolve() != path:
                raise OSError('材料路径包含符号链接，未删除')
            path.unlink(missing_ok=True)
            if item['kind'] == 'blob':
                db.execute('DELETE FROM blobs WHERE sha256=?', (sha,))
            else:
                mapping_path = app.data_dir / 'restored-assets.json'
                if mapping_path.exists():
                    if mapping_path.is_symlink() or mapping_path.resolve() != mapping_path:
                        raise OSError('恢复映射路径不安全')
                    mapping = json.loads(mapping_path.read_text())
                    if not isinstance(mapping, dict):
                        raise ValueError('恢复映射格式无效')
                    mapping = {k: v for k, v in mapping.items() if v != relative}
                    fd, temporary = tempfile.mkstemp(dir=app.data_dir, prefix='.purge-assets-')
                    try:
                        with os.fdopen(fd, 'w') as out:
                            out.write(canonical(mapping))
                            out.flush()
                            os.fsync(out.fileno())
                        os.replace(temporary, mapping_path)
                    finally:
                        Path(temporary).unlink(missing_ok=True)
            db.execute('COMMIT')
        except (OSError, ValueError) as exc:
            db.execute('ROLLBACK')
            left.append(item)
            errors.append({'file': relative, 'message': str(exc)})
        except BaseException:
            db.execute('ROLLBACK')
            raise
    result.update(files_pending=len(left), cleanup_errors=errors, complete=not left)
    db.execute('UPDATE purge_requests SET pending_json=?,result_json=? WHERE request_id=?',
               (canonical(left), canonical(result), request_id))
    return result


def execute(app, command, p, pid, request_id):
    kind = command.split('.')[0]
    from jsonschema import Draft202012Validator
    contract = json.loads((Path(__file__).parent/'contracts/purge-input.schema.json').read_text())
    if not Draft202012Validator(contract['$defs'][kind+'Purge']).is_valid(p):
        raise YuError('INVALID_INPUT','硬删除输入不符合契约；请查阅对应 purge 输入字段。')
    key = KEYS[kind]
    allowed = {'dry_run', 'confirm_id', 'plan_hash', 'reason', 'schedulers_handled'} | ({key} if key else set())
    if not isinstance(p, dict) or set(p) - allowed or type(p.get('dry_run', True)) is not bool:
        raise YuError('INVALID_INPUT', '硬删除输入无效；默认 dry_run=true，仅预览。')
    if len(canonical(p).encode()) > 8 * 1024 * 1024:
        raise YuError('INPUT_TOO_LARGE', '单次 JSON 不能超过 8 MiB。')
    if kind == 'library' and pid is not None:
        raise YuError('INVALID_INPUT', '案例库属于工作空间，不接受 --project。')
    ident = p.get(key) if key else pid
    if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}', ident) or (kind != 'library' and not isinstance(pid, str)):
        raise YuError('INVALID_INPUT', '需要真实目标 ID 和项目范围。')
    dry = p.get('dry_run', True)
    if not dry:
        if p.get('confirm_id') != ident or not isinstance(p.get('plan_hash'), str) or not re.fullmatch('[0-9a-f]{64}', p['plan_hash']) or not isinstance(p.get('reason'), str) or not p['reason'].strip():
            raise YuError('INVALID_INPUT', '执行需要预览返回的 plan_hash、匹配的 confirm_id 和删除原因。')
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}', request_id):
            raise YuError('INVALID_INPUT', '执行硬删除需要 request-id。')
    from .collaboration import lock
    with lock(app, pid) if pid else nullcontext():
        with storage_lock(app):
            db = app.db
            fingerprint = digest({'command': command, 'project_id': pid, 'input': p})
            db.execute('BEGIN IMMEDIATE' if not dry else 'BEGIN')
            try:
                receipt = db.execute('SELECT * FROM purge_requests WHERE request_id=?', (request_id,)).fetchone() if not dry else None
                if receipt:
                    if receipt['request_hash'] != fingerprint:
                        raise YuError('IDEMPOTENCY_CONFLICT', 'request-id 已用于不同硬删除请求。')
                    db.execute('COMMIT')
                    return app._envelope(command, pid, request_id, cleanup_files(app, request_id), replayed=True)
                preview, chosen, files, identities = plan(app, kind, pid, ident)
                if dry:
                    db.execute('COMMIT')
                    return app._envelope(command, pid, None, preview)
                if preview['plan_hash'] != p['plan_hash']:
                    raise YuError('BASE_REVISION_CONFLICT', '删除范围或引用已变化，请重新预览。')
                if preview['blockers']:
                    raise YuError('PURGE_REFERENCED', '目标仍被引用或正在使用，未删除任何内容。', details=preview['blockers'])
                if preview['scheduler_actions'] and p.get('schedulers_handled') is not True:
                    raise YuError('PURGE_SCHEDULES_ACTIVE', '先通过宿主工具停止所列定时任务，再提交 schedulers_handled=true。', details=preview['scheduler_actions'])
                # Drop guards only inside this transaction; concurrent connections cannot
                # observe the intermediate schema. FK enforcement stays enabled/deferred.
                db.execute('PRAGMA defer_foreign_keys=ON')
                triggers = [dict(r) for r in db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")]
                for trigger in triggers:
                    db.execute('DROP TRIGGER ' + quoted(trigger['name']))
                for table, rows in chosen.items():
                    for row in rows.values():
                        if table == 'changes':
                            ns = 'project.create' if row['command'] == 'project.create' else pid
                            db.execute('INSERT OR IGNORE INTO purged_requests VALUES(?,?)', (ns, row['request_id']))
                        db.execute(f'DELETE FROM {quoted(table)} WHERE rowid=?', (row['_rowid'],))
                for identity in identities:
                    db.execute('INSERT OR IGNORE INTO purge_tombstones VALUES(?,?,?,?)', (identity, kind, pid, now()))
                # Remove old success payloads, preventing stale replays from claiming a
                # deleted source/object/library still exists. Keep only minimal receipts.
                for table in ('changes', 'case_library_requests'):
                    for row in db.execute(f'SELECT rowid AS _rowid,* FROM {table}').fetchall():
                        if refers(json.loads(row['result_json']), identities):
                            db.execute(f'UPDATE {table} SET result_json=? WHERE rowid=?',
                                       (canonical({'effect': 'purged', 'retained_data': False, 'deletion_mode': 'hard'}), row['_rowid']))
                            if table == 'changes':
                                db.execute("UPDATE changes SET reason='关联内容已硬删除' WHERE rowid=?", (row['_rowid'],))
                for trigger in triggers:
                    db.execute(trigger['sql'])
                if db.execute('PRAGMA foreign_key_check').fetchone():
                    raise YuError('INTEGRITY_FAILURE', '硬删除后引用检查失败，已回滚。')
                result = {'deletion_mode': 'hard', 'target_id': ident, 'project_id': pid, 'effect': 'purged',
                          'retained_data': False, 'records_deleted': preview['records'],
                          'history_receipts_redacted': preview['history_receipts_redacted'],
                          'shared_files_retained': preview['shared_files_retained'],
                          'managed_files_to_delete': preview['managed_files_to_delete'],
                          'preview_caches_to_clear': preview['preview_caches_to_clear'],
                          'files_pending': len(files), 'complete': False}
                db.execute('INSERT INTO purge_requests VALUES(?,?,?,?,?)',
                           (request_id, fingerprint, canonical(result), canonical(files), now()))
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
            return app._envelope(command, pid, request_id, cleanup_files(app, request_id))
