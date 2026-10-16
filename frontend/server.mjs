/** Mock preview only. No database, CLI invocation, or external request. */
import { createServer } from 'node:http';
import { readFile, realpath, stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const PUBLIC = resolve(fileURLToPath(new URL('./public/', import.meta.url)));
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml' };
export function createPreviewServer() {
  return createServer(async (req, res) => {
    const send = (status, body, headers = {}) => {
      res.writeHead(status, { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Yu-Mode': 'mock-read-only', ...headers });
      res.end(req.method === 'HEAD' ? undefined : body);
    };
    if (!['GET', 'HEAD'].includes(req.method)) {
      return send(405, 'Read-only preview', { Allow: 'GET, HEAD' });
    }
    let pathname;
    try { pathname = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname); }
    catch { return send(400, 'Bad request'); }
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
