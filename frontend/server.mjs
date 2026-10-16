/** Mock preview only. No database or Yu+ CLI access; optional local Finder bridge. */
import { createServer } from 'node:http';
import { createLocalFiles } from './local-files.mjs';
import { readFile, realpath, stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const PUBLIC = resolve(fileURLToPath(new URL('./public/', import.meta.url)));
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml' };
export function createPreviewServer(options = {}) {
  const localFiles = createLocalFiles(options.localFiles);
  return createServer(async (req, res) => {
    const send = (status, body, headers = {}) => {
      res.writeHead(status, { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Yu-Mode': 'mock-read-only', ...headers });
      res.end(req.method === 'HEAD' ? undefined : body);
    };
    let pathname;
    try { pathname = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname); }
    catch { return send(400, 'Bad request'); }
    if (pathname === '/api/health' && req.method === 'GET') return send(200, JSON.stringify({mode:'demo'}), {'Content-Type':'application/json; charset=utf-8'});
    if (pathname === '/api/local-files' || pathname === '/api/local-files/reveal') {
      const json = (status, data) => send(status, JSON.stringify(data), {'Content-Type':'application/json; charset=utf-8'});
      const port = req.socket.localPort;
      const hosts = [`127.0.0.1:${port}`, `localhost:${port}`];
      const origin = req.headers.origin;
      if (!hosts.includes(req.headers.host) || (origin && origin !== `http://${req.headers.host}`) ||
          (req.headers['sec-fetch-site'] && req.headers['sec-fetch-site'] !== 'same-origin' && req.headers['sec-fetch-site'] !== 'none')) {
        return json(403, {message:'只允许本机页面访问'});
      }
      try {
        if (pathname === '/api/local-files' && req.method === 'GET') return json(200, await localFiles.list());
        if (pathname !== '/api/local-files/reveal' || req.method !== 'POST') return json(405, {message:'不支持此操作'});
        if (origin !== `http://${req.headers.host}` || req.headers['content-type']?.split(';')[0] !== 'application/json') return json(403, {message:'仅接受同源页面操作'});
        if (Number(req.headers['content-length']) > 2048) return json(413, {message:'请求过大'});
        const chunks = []; let size = 0;
        for await (const chunk of req) {
          size += chunk.length;
          if (size > 2048) return json(413, {message:'请求过大'});
          chunks.push(chunk);
        }
        let data;
        try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { return json(400, {message:'无效请求'}); }
        if (!data || Object.keys(data).some(key=>!['versionId','assetId'].includes(key)) ||
            typeof data.versionId !== 'string' || typeof data.assetId !== 'string') return json(400, {message:'只接受附件标识'});
        const result = await localFiles.reveal(data.versionId, data.assetId);
        return json(result.status, {message:result.message});
      } catch { return json(500, {message:'本地文件服务暂不可用'}); }
    }
    if (!['GET', 'HEAD'].includes(req.method)) return send(405, 'Read-only preview', { Allow:'GET, HEAD' });
    if (pathname.includes('\0') || pathname.includes('\\')) return send(400, 'Bad request');
    if (pathname === '/') pathname = '/index.html';
    const target = resolve(PUBLIC, '.' + pathname);
    const inside = (p) => p.startsWith(PUBLIC + sep);
    if (!inside(target)) return send(403, 'Forbidden');
    try {
      const actual = await realpath(target);
      if (!inside(actual)) return send(403, 'Forbidden');
      if (!(await stat(actual)).isFile()) return send(404, 'Not found');
      const mime = TYPES[extname(actual)];
      if (!mime) return send(404, 'Not found');
      const data = req.method === 'HEAD' ? undefined : await readFile(actual);
      send(200, data, { 'Content-Type': mime });
    } catch { send(404, 'Not found'); }
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args.length && (args.length !== 2 || args[0] !== '--port')) {
    throw new Error('Usage: node server.mjs [--port 7801]');
  }
  const port = Number(args[1] ?? 7801);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid port');
  const server = createPreviewServer();
  server.on('error', (error) => { console.error(error.message); process.exitCode = 1; });
  server.listen(port, '127.0.0.1', () => console.log(`Yu+ 模拟数据预览 http://127.0.0.1:${port}\n仅本机访问 · 不连接数据库或飞书`));
}
