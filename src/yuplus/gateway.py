"""Loopback gateway; source preferences are the only browser business writes."""
import json
import os
import threading
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from urllib.parse import parse_qs, quote, unquote, urlsplit

from .browser_view import (asset_availability, browser_view, is_original_local_asset, open_verified_asset,
                           read_snapshot, registered_asset, require_project)
from .core import YuError
from .source import _assets_from_db

SAFE_INLINE = {'application/pdf', 'text/plain', 'text/markdown', 'application/json',
               'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/avif',
               'audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/ogg',
               'video/mp4', 'video/webm', 'video/ogg'}


def frontend_root():
    repository = Path(__file__).resolve().parents[2] / 'frontend/public'
    return repository if repository.is_dir() else Path(__file__).parent / 'web'


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, data_dir, port=7801, static_dir=None):
        if not 0 <= port <= 65535:
            raise YuError('INVALID_INPUT', '端口须在 0–65535 之间。')
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.static_dir = Path(static_dir or frontend_root()).resolve()
        if not (self.static_dir / 'index.html').is_file():
            raise YuError('FILE_NOT_FOUND', '未安装可视化页面资源。')
        super().__init__(('127.0.0.1', port), GatewayHandler)
        self.url = f'http://127.0.0.1:{self.server_port}'
        from .case_preview import PreviewCache
        self.case_previews = PreviewCache(self.data_dir)


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = 'YuPlus/1'
    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('X-Frame-Options', 'DENY')
        super().end_headers()

    def json_response(self, value, status=200):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def error(self, code, message, status):
        self.json_response({'ok': False, 'error': {'code': code, 'message': message}}, status)

    def trusted(self):
        hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        host_values = self.headers.get_all('Host', [])
        if len(host_values) != 1 or host_values[0] not in hosts:
            self.error('FORBIDDEN', '拒绝非本地 Host。', 403); return False
        origins = self.headers.get_all('Origin', [])
        if len(origins) > 1 or (origins and origins[0] != f'http://{host_values[0]}'):
            self.error('FORBIDDEN', '拒绝跨来源请求。', 403); return False
        if self.headers.get('Sec-Fetch-Site', 'none') not in {'none', 'same-origin'}:
            self.error('FORBIDDEN', '拒绝跨来源请求。', 403); return False
        return True

    def dispatch(self):
        if not self.trusted(): return
        try:
            url = urlsplit(self.path)
            if url.scheme or url.netloc:
                raise YuError('INVALID_INPUT', '请求路径无效。')
            self.route(url)
        except YuError as exc:
            status = 404 if exc.code.endswith('_NOT_FOUND') else 409 if exc.code in {'FILE_HASH_MISMATCH', 'INTEGRITY_FAILURE'} else 400
            status = {'AUTH_REQUIRED':401,'FORBIDDEN':403,'FEISHU_UNAVAILABLE':503,'PREVIEW_BUSY':503,
                      'VERSION_CONFLICT':409,'IDEMPOTENCY_CONFLICT':409,'ALREADY_EXISTS':409}.get(exc.code,status)
            self.error(exc.code, exc.message, status)
        except (sqlite3.DatabaseError, OSError, subprocess.SubprocessError) as exc:
            if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
                return
            self.error('UNAVAILABLE', '数据或文件暂时不可读取，原文件已保留。', 503)
        except (ValueError, TypeError, KeyError, UnicodeError):
            self.error('INVALID_INPUT', '请求格式不正确。', 400)

    def params(self, url, allowed, required=()):
        query = parse_qs(url.query, keep_blank_values=True, max_num_fields=8)
        if set(query) - set(allowed) or any(len(v) != 1 or not v[0] for v in query.values()) or any(key not in query for key in required):
            raise YuError('INVALID_INPUT', '参数无效或缺失。')
        return {key: values[0] for key, values in query.items()}

    def route(self, url):
        path = unquote(url.path)
        if self.command == 'POST' and path == '/api/local-files/reveal':
            return self.reveal()
        if self.command == 'POST' and path == '/api/libraries':
            self.params(url, set())
            return self.library_write()
        if self.command not in {'GET', 'HEAD'}:
            return self.error('METHOD_NOT_ALLOWED', '本地浏览器不提供业务写入接口。', 405)
        if path == '/api/health':
            with read_snapshot(self.server.data_dir) as db:
                db.execute('SELECT id FROM projects LIMIT 1').fetchall()
            return self.json_response({'ok': True, 'mode': 'live', 'api_version': '1',
                'data_dir': str(self.server.data_dir), 'url': self.server.url, 'port': self.server.server_port, 'pid': os.getpid(), 'instance_id': os.environ.get('YUPLUS_SERVICE_INSTANCE')})
        if path == '/api/view':
            query = self.params(url, {'project'})
            with read_snapshot(self.server.data_dir) as db:
                view = browser_view(db, self.server.data_dir, query.get('project'))
            for record in view.get('case_findings',[]):
                record['preview'] = self.server.case_previews.cached(record)
            return self.json_response(view)
        if path == '/api/case-finding/preview':
            query = self.params(url, {'project','version'}, ('project','version'))
            from .case_research import get
            with read_snapshot(self.server.data_dir) as db:
                require_project(db,query['project'])
                record = get(db,query['project'],query['version'])
            if self.command == 'HEAD':
                return self.json_response(self.server.case_previews.cached(record) or {})
            return self.json_response(self.server.case_previews.refresh(record))
        if path.startswith('/api/case-finding/images/'):
            self.params(url, set())
            with read_snapshot(self.server.data_dir) as db:
                raw,mime = self.server.case_previews.image(db,path.rsplit('/',1)[-1])
            self.send_response(200)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            if self.command != 'HEAD':self.wfile.write(raw)
            return
        if path == '/api/logo':
            self.params(url, {'v'})
            from .appearance import image_bytes
            with read_snapshot(self.server.data_dir) as db:
                raw = image_bytes(db)
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            if self.command != 'HEAD': self.wfile.write(raw)
            return
        if path == '/api/assets':
            query = self.params(url, {'project', 'version', 'asset', 'download'}, ('project', 'version', 'asset'))
            if 'download' in query and query['download'] != '1':
                raise YuError('INVALID_INPUT', '下载参数无效。')
            with read_snapshot(self.server.data_dir) as db:
                asset = registered_asset(db, query['project'], query['version'], query['asset'])
            stream, _ = open_verified_asset(self.server.data_dir, asset)
            with stream:
                return self.stream_asset(stream, asset, download=query.get('download') == '1')
        if path == '/api/local-files':
            query = self.params(url, {'project'}, ('project',))
            supported = sys.platform == 'darwin' and shutil.which('open') is not None
            files = []
            with read_snapshot(self.server.data_dir) as db:
                require_project(db, query['project'])
                if supported:
                    for row in db.execute('SELECT id FROM source_versions WHERE project_id=? AND sealed=1', (query['project'],)):
                        for asset in _assets_from_db(db, query['project'], row['id']):
                            if is_original_local_asset(self.server.data_dir, asset) and asset_availability(self.server.data_dir, asset) == 'available':
                                files.append({'projectId': query['project'], 'versionId': row['id'], 'assetId': asset['asset_id'],
                                              'source_version_id': row['id'], 'asset_id': asset['asset_id']})
            return self.json_response({'supported': supported, 'files': files})
        if path.startswith('/api/'):
            return self.error('NOT_FOUND', '接口不存在。', 404)
        if '\\' in path or '\x00' in path or any(piece in {'.', '..'} for piece in path.split('/')):
            return self.error('FORBIDDEN', '路径不允许。', 403)
        target = (self.server.static_dir / (path.lstrip('/') or 'index.html')).resolve()
        if not target.is_relative_to(self.server.static_dir):
            return self.error('FORBIDDEN', '路径不允许。', 403)
        if not target.is_file():
            return self.error('NOT_FOUND', '页面不存在。', 404)
        content = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(target)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(content)

    def library_write(self):
        if self.headers.get('Origin') != f"http://{self.headers['Host']}":
            return self.error('FORBIDDEN', '案例库设置需要同源请求。', 403)
        if self.headers.get_content_type() != 'application/json' or self.headers.get('Transfer-Encoding'):
            return self.error('INVALID_INPUT', '需要 JSON 请求。', 400)
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= 16384:
            return self.error('INVALID_INPUT', 'JSON 请求长度无效。', 400)
        from .cli import parse_json
        body = parse_json(self.rfile.read(int(lengths[0])).decode('utf-8'))
        if not isinstance(body, dict) or set(body) != {'request_id', 'action', 'input'} or body['action'] not in ('add', 'delete', 'restore'):
            raise YuError('INVALID_INPUT', '仅支持添加、移除或重新添加案例库源。')
        if not isinstance(body['input'], dict) or set(body['input']) & {'api_version', 'command'}:
            raise YuError('INVALID_INPUT', '无效案例库输入。')
        from .app import App
        from .case_library import catalog
        app = App(self.server.data_dir)
        try:
            command = 'library.' + body['action']
            result = app.execute(command, {'api_version': '1', 'command': command, **body['input']}, request_id=body['request_id'])
            result['libraries'] = catalog(app.db)
            return self.json_response(result)
        finally:
            app.close()

    def reveal(self):
        # POST requires an explicit same-origin Origin in addition to the common checks.
        if self.headers.get('Origin') != f"http://{self.headers['Host']}":
            return self.error('FORBIDDEN', '定位文件需要同源请求。', 403)
        if self.headers.get_content_type() != 'application/json' or self.headers.get('Transfer-Encoding'):
            return self.error('INVALID_INPUT', '需要 JSON 请求。', 400)
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= 4096:
            return self.error('INVALID_INPUT', 'JSON 请求长度无效。', 400)
        from .cli import parse_json
        payload = parse_json(self.rfile.read(int(lengths[0])).decode('utf-8'))
        if not isinstance(payload, dict) or set(payload) != {'projectId', 'versionId', 'assetId'} or not all(isinstance(v, str) for v in payload.values()):
            raise YuError('INVALID_INPUT', '仅接受登记的项目、版本及资产 ID。')
        with read_snapshot(self.server.data_dir) as db:
            asset = registered_asset(db, payload['projectId'], payload['versionId'], payload['assetId'])
        if not is_original_local_asset(self.server.data_dir, asset):
            raise YuError('INVALID_INPUT', '此附件保存在材料库中，请下载文件；不能在 Finder 中定位内部存储文件。')
        stream, path = open_verified_asset(self.server.data_dir, asset)
        stream.close()
        if sys.platform != 'darwin' or not shutil.which('open'):
            return self.error('UNSUPPORTED', '当前平台不支持 Finder 定位。', 501)
        result = subprocess.run(['open', '-R', str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        if result.returncode:
            return self.error('UNAVAILABLE', '无法定位此文件。', 503)
        return self.json_response({'ok': True})

    def stream_asset(self, stream, asset, download=False):
        size = asset['size_bytes']
        start, end, status = 0, size - 1, 200
        range_header = self.headers.get('Range')
        if range_header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
            if match and any(match.groups()):
                left, right = match.groups()
                if left:
                    start, end = int(left), min(int(right), size - 1) if right else size - 1
                else:
                    start, end = max(0, size - int(right)), size - 1
                valid = start <= end and start < size and (bool(left) or int(right) > 0)
            else:
                valid = False
            if not valid:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0'); self.end_headers(); return
            status = 206
        mime = asset['mime_type'].split(';')[0].strip().lower()
        safe = mime in SAFE_INLINE
        self.send_response(status)
        self.send_header('Content-Type', mime if safe else 'application/octet-stream')
        self.send_header('Content-Disposition', ('inline' if safe and not download else 'attachment') + "; filename*=UTF-8''" + quote(asset['display_name'], safe=''))
        self.send_header('Content-Security-Policy', "sandbox; default-src 'none'")
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(max(0, end - start + 1)))
        if status == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command == 'HEAD': return
        stream.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk: break
            self.wfile.write(chunk)
            remaining -= len(chunk)

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = dispatch


def serve(data_dir, port=7801):
    with GatewayServer(data_dir, port) as server:
        from .service import register
        from .source_check import startup_scan
        register(server)
        from .collaboration import poll
        stop_collaboration = threading.Event()
        threading.Thread(target=poll,args=(server.data_dir,stop_collaboration),daemon=True).start()
        threading.Thread(target=startup_scan,args=(server.data_dir,),daemon=True).start()
        print(json.dumps({'api_version': '1', 'command': 'serve', 'ok': True,
                          'data': {'url': server.url, 'data_dir': str(server.data_dir), 'port': server.server_port, 'mode': 'live'}}, ensure_ascii=False), flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            stop_collaboration.set()
    return 0
