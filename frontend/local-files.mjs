/** Finder bridge for generated preview snapshots; never accepts filesystem paths from HTTP. */
import { mkdir, realpath, stat, writeFile } from 'node:fs/promises';
import { basename, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import DATA from './public/data/demo.js';

const run = promisify(execFile);
const CACHE = fileURLToPath(new URL('./.preview/source-files/', import.meta.url));
export function createLocalFiles({ platform = process.platform, cacheRoot = CACHE,
  reveal = (path) => run('/usr/bin/open', ['-R', path], { timeout:5000 }) } = {}) {
  let files;
  const inside = (path, root) => path.startsWith(root + sep);
  async function registeredFiles() {
    if (files) return files;
    files = (async () => {
      await mkdir(cacheRoot, {recursive:true});
      const root = await realpath(cacheRoot);
      const result = new Map();
      for (const version of DATA.source_versions) for (const asset of version.assets) {
        if (!version.body_text || !['body','transcript'].includes(asset.role) ||
            !['text/plain','text/markdown'].includes(asset.mime_type) || asset.availability !== 'local_copy') continue;
        if (basename(asset.display_name) !== asset.display_name || !/^[a-zA-Z0-9_-]+$/.test(version.id)) continue;
        const folder = resolve(root, version.id);
        await mkdir(folder, {recursive:true});
        if (!inside(await realpath(folder), root)) continue;
        const path = resolve(folder, asset.display_name);
        if (!inside(path, root)) continue;
        try { await writeFile(path, version.body_text, {encoding:'utf8', flag:'wx', mode:0o600}); }
        catch (error) { if (error.code !== 'EEXIST') throw error; }
        const actual = await realpath(path);
        if (!inside(actual, root) || !(await stat(actual)).isFile()) continue;
        result.set(`${version.id}/${asset.asset_id}`, {versionId:version.id, assetId:asset.asset_id, path, root});
      }
      return result;
    })().catch((error) => { files = undefined; throw error; });
    return files;
  }
  return {
    async list() {
      if (platform !== 'darwin') return { supported:false, files:[] };
      const all = await registeredFiles();
      return { supported:true, files:[...all.values()].map(({versionId,assetId})=>({versionId,assetId})) };
    },
    async reveal(versionId, assetId) {
      if (platform !== 'darwin') return {status:501,message:'此环境不支持 Finder'};
      const file = (await registeredFiles()).get(`${versionId}/${assetId}`);
      if (!file) return {status:404,message:'此附件没有可定位的本地文件'};
      try {
        const actual = await realpath(file.path);
        if (!inside(actual, file.root) || !(await stat(actual)).isFile()) return {status:404,message:'本地文件不可用'};
        await reveal(actual);
        return {status:200,message:'已在 Finder 中显示'};
      } catch (error) {
        return {status:error.code === 'ENOENT' ? 404 : 500,message:error.code === 'ENOENT' ? '本地文件已被移走，暂时无法定位' : '无法打开 Finder，请稍后重试'};
      }
    },
  };
}
