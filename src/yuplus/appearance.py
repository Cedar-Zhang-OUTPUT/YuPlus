"""Small workspace avatar, stored atomically in SQLite and included in backups."""
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib
from .core import YuError, canonical, digest, now

MAX_BYTES = 256 * 1024
PNG = b'\x89PNG\r\n\x1a\n'


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS workspace_logo (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, png BLOB, sha256 TEXT, updated_at TEXT NOT NULL) STRICT')
    db.execute('CREATE TABLE IF NOT EXISTS logo_requests (request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result_json TEXT NOT NULL) STRICT')
    db.execute('PRAGMA user_version=6')


def row(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='workspace_logo'").fetchone(): return None
    return db.execute('SELECT * FROM workspace_logo WHERE singleton=1').fetchone()


def metadata(db):
    current = row(db)
    version = current['version'] if current else 0
    custom = bool(current and current['png'])
    return {'version': version, 'custom': custom, 'url': f'/api/logo?v={version}' if custom else None,
            'updated_at': current['updated_at'] if current else None}


def image_bytes(db):
    current = row(db)
    if not current or not current['png']: raise YuError('LOGO_NOT_FOUND', '当前使用默认 Logo。')
    raw = current['png']
    if hashlib.sha256(raw).hexdigest() != current['sha256']:
        raise YuError('INTEGRITY_FAILURE', '头像内容校验失败。')
    return raw


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def normalize_png(raw):
    """Validate bounded static PNG data, strip ancillary metadata and recompress."""
    def invalid(): raise YuError('INVALID_INPUT', '请先将图片压缩为不超过 512×512、256 KiB 的静态 8-bit 非交错 PNG；保留原图。')
    if len(raw) > MAX_BYTES or not raw.startswith(PNG): invalid()
    pos = 8; chunks = []; compressed = b''; ihdr = None; ended = False; idat_closed = False
    while pos < len(raw):
        if pos + 12 > len(raw): invalid()
        size = struct.unpack('>I', raw[pos:pos+4])[0]
        kind = raw[pos+4:pos+8]; data = raw[pos+8:pos+8+size]
        end = pos + 12 + size
        if end > len(raw) or zlib.crc32(kind+data) != struct.unpack('>I', raw[end-4:end])[0]: invalid()
        if ihdr is None and kind != b'IHDR': invalid()
        if kind == b'IHDR':
            if ihdr is not None or size != 13: invalid()
            ihdr = data
            width, height, depth, color, compression, filter_, interlace = struct.unpack('>IIBBBBB', data)
            if not (0 < width <= 512 and 0 < height <= 512) or depth != 8 or color not in (0,2,3,4,6) or compression or filter_ or interlace: invalid()
        elif kind == b'IDAT':
            if idat_closed: invalid()
            compressed += data
        elif kind == b'IEND':
            if size or end != len(raw): invalid()
            ended = True; break
        elif kind in (b'acTL', b'fcTL', b'fdAT'): invalid()
        elif kind in (b'PLTE', b'tRNS'):
            if compressed or any(k == kind for k, _ in chunks): invalid()
            if kind == b'PLTE' and (not size or size % 3 or size > 768): invalid()
            chunks.append((kind, data))
        elif kind[0] & 32 == 0: invalid()  # unknown critical chunk
        if compressed and kind != b'IDAT': idat_closed = True
        pos = end
    if not ended or not compressed: invalid()
    if color == 3 and not any(k == b'PLTE' for k, _ in chunks): invalid()
    channels = {0:1,2:3,3:1,4:2,6:4}[color]; stride = 1 + width * channels
    expected = height * stride
    try:
        decoder = zlib.decompressobj(); pixels = decoder.decompress(compressed, expected+1)
        if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail: invalid()
    except zlib.error: invalid()
    if any(pixels[i] > 4 for i in range(0, len(pixels), stride)): invalid()
    result = PNG + chunk(b'IHDR', ihdr) + b''.join(chunk(k,d) for k,d in chunks) + chunk(b'IDAT', zlib.compress(pixels,9)) + chunk(b'IEND',b'')
    if len(result) > MAX_BYTES: invalid()
    return result


def execute(app, command, payload, project_id, request_id):
    if project_id is not None: raise YuError('INVALID_INPUT', 'Logo 属于当前数据目录的全局设置，不接受 --project。')
    if command == 'logo.show':
        if payload: raise YuError('INVALID_INPUT', 'logo show 不接受额外输入。')
        return app._envelope(command, None, None, metadata(app.db))
    if command not in ('logo.set','logo.reset') or not isinstance(payload,dict): raise YuError('INVALID_INPUT', '无效 Logo 操作。')
    allowed = {'api_version','command','base_version'} | ({'local_path'} if command == 'logo.set' else set())
    if set(payload) != allowed or payload.get('api_version') != '1' or payload.get('command') != command or type(payload.get('base_version')) is not int or payload['base_version'] < 0:
        raise YuError('INVALID_INPUT', '需要匹配的 command、api_version: 1、当前 base_version；set 另需 local_path。')
    if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}',request_id): raise YuError('INVALID_INPUT','写操作需要合法 --request-id。')
    fingerprint = digest(payload)
    app.db.execute('BEGIN IMMEDIATE')
    try:
        receipt = app.db.execute('SELECT * FROM logo_requests WHERE request_id=?',(request_id,)).fetchone()
        if receipt:
            if receipt['request_hash'] != fingerprint: raise YuError('IDEMPOTENCY_CONFLICT','request-id 已用于不同输入。')
            data=json.loads(receipt['result_json']); replayed=True
        else:
            if metadata(app.db)['version'] != payload['base_version']: raise YuError('BASE_REVISION_CONFLICT','头像已变化，请重新读取 logo show。')
            raw = None
            if command == 'logo.set':
                path = payload['local_path']
                if not isinstance(path,str) or not path or '\0' in path: raise YuError('INVALID_INPUT','local_path 必须是 PNG 文件路径。')
                file = Path(path).expanduser()
                if not file.is_file(): raise YuError('FILE_NOT_FOUND','头像文件不存在或不是普通文件。')
                with file.open('rb') as stream: raw = normalize_png(stream.read(MAX_BYTES+1))
            app.db.execute('INSERT INTO workspace_logo VALUES(1,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET version=excluded.version,png=excluded.png,sha256=excluded.sha256,updated_at=excluded.updated_at',
                (payload['base_version']+1,raw,hashlib.sha256(raw).hexdigest() if raw else None,now()))
            data=metadata(app.db); replayed=False
            app.db.execute('INSERT INTO logo_requests VALUES(?,?,?)',(request_id,fingerprint,canonical(data)))
        app.db.execute('COMMIT')
    except BaseException:
        app.db.execute('ROLLBACK'); raise
    return app._envelope(command,None,request_id,data,replayed=replayed)
