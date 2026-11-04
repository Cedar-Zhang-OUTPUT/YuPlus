"""Agent-reported Eagle observations, never a probe of the MCP runtime."""
from datetime import datetime, timezone, timedelta
import json
import re
from .core import YuError, canonical, digest, now

STATES = {'not_configured', 'configured', 'waiting', 'connected', 'verified', 'unavailable'}
READS = {'unverified', 'metadata', 'thumbnail', 'original'}


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS eagle_connection (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, observation_json TEXT NOT NULL, updated_at TEXT NOT NULL) STRICT')
    db.execute('CREATE TABLE IF NOT EXISTS eagle_requests (request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result_json TEXT NOT NULL) STRICT')
    db.execute('PRAGMA user_version=12')


def status(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='eagle_connection'").fetchone():
        row = db.execute('SELECT * FROM eagle_connection WHERE singleton=1').fetchone()
        if row:
            return {**json.loads(row['observation_json']), 'version': row['version'], 'updated_at': row['updated_at']}
    return {'version': 0, 'state': 'not_configured', 'observed_at': None, 'updated_at': None,
            'library_name': '', 'library_key': '', 'server_name': '', 'material_read': 'unverified'}


def validate(payload):
    fields = {'api_version', 'command', 'base_version', 'state', 'observed_at', 'library_name',
              'library_key', 'server_name', 'material_read', 'tools_listed', 'query_succeeded', 'target_confirmed'}
    def invalid():
        raise YuError('INVALID_INPUT', 'Eagle 状态需要完整的观察记录、当前 base_version 与匹配的验证证据；不接受配置或凭据。')
    if not isinstance(payload, dict) or set(payload) != fields: invalid()
    if payload['api_version'] != '1' or payload['command'] != 'eagle.record': invalid()
    if type(payload['base_version']) is not int or payload['base_version'] < 0: invalid()
    if not isinstance(payload['state'], str) or payload['state'] not in STATES: invalid()
    if not isinstance(payload['material_read'], str) or payload['material_read'] not in READS: invalid()
    for key in ('tools_listed', 'query_succeeded', 'target_confirmed'):
        if type(payload[key]) is not bool: invalid()
    for key in ('library_name', 'library_key', 'server_name'):
        value = payload[key]
        if not isinstance(value, str) or len(value) > 200 or value != value.strip() or any(ord(c) < 32 for c in value): invalid()
    # No endpoints, local paths or raw configuration are needed for display.
    if any(c in payload['library_key'] for c in '/\\?@') or any(c in payload['server_name'] for c in '/\\?@'): invalid()
    try:
        stamp = datetime.fromisoformat(payload['observed_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc) + timedelta(minutes=5): invalid()
    except (ValueError, TypeError, AttributeError): invalid()
    connected = payload['state'] in {'connected', 'verified'}
    if connected and not (payload['tools_listed'] and payload['query_succeeded'] and payload['library_name'] and payload['library_key'] and payload['server_name']): invalid()
    if payload['state'] == 'verified' and not (payload['target_confirmed'] and payload['material_read'] in {'thumbnail', 'original'}): invalid()
    if payload['material_read'] != 'unverified' and not (connected and payload['query_succeeded']): invalid()
    if payload['material_read'] in {'thumbnail', 'original'} and not payload['target_confirmed']: invalid()
    if not connected and any(payload[k] for k in ('query_succeeded', 'target_confirmed')): invalid()


def execute(app, command, payload, project_id, request_id):
    if project_id is not None: raise YuError('INVALID_INPUT', 'Eagle 状态属于当前数据目录，不接受 --project。')
    if command == 'eagle.status':
        if payload: raise YuError('INVALID_INPUT', 'eagle status 不接受额外输入。')
        return app._envelope(command, None, None, status(app.db))
    if command != 'eagle.record': raise YuError('INVALID_INPUT', '无效 Eagle 状态操作。')
    validate(payload)
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}', request_id):
        raise YuError('INVALID_INPUT', '写操作需要合法 --request-id。')
    fingerprint = digest(payload)
    app.db.execute('BEGIN IMMEDIATE')
    try:
        receipt = app.db.execute('SELECT * FROM eagle_requests WHERE request_id=?', (request_id,)).fetchone()
        if receipt:
            if receipt['request_hash'] != fingerprint: raise YuError('IDEMPOTENCY_CONFLICT', 'request-id 已用于不同输入。')
            data = json.loads(receipt['result_json']); replayed = True
        else:
            current = status(app.db)
            if current['version'] != payload['base_version']: raise YuError('BASE_REVISION_CONFLICT', 'Eagle 状态已变化，请重新读取 eagle status。')
            if current['observed_at'] and datetime.fromisoformat(payload['observed_at'].replace('Z', '+00:00')) < datetime.fromisoformat(current['observed_at'].replace('Z', '+00:00')):
                raise YuError('BASE_REVISION_CONFLICT', '不能用较早的观察覆盖较新的 Eagle 状态。')
            observation = {k: v for k, v in payload.items() if k not in {'api_version', 'command', 'base_version'}}
            app.db.execute('INSERT INTO eagle_connection VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET version=excluded.version,observation_json=excluded.observation_json,updated_at=excluded.updated_at',
                           (current['version'] + 1, canonical(observation), now()))
            data = status(app.db); replayed = False
            app.db.execute('INSERT INTO eagle_requests VALUES(?,?,?)', (request_id, fingerprint, canonical(data)))
        app.db.execute('COMMIT')
    except BaseException:
        app.db.execute('ROLLBACK'); raise
    return app._envelope(command, None, request_id, data, replayed=replayed)
