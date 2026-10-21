import * as vocabulary from './vocabulary.js';

export function hydrateView(raw) {
  if (!raw?.meta || raw.meta.demo !== false || !Array.isArray(raw.projects) ||
      !Array.isArray(raw.objects) || !Array.isArray(raw.object_revisions) ||
      !Array.isArray(raw.sources) || !Array.isArray(raw.source_versions)) {
    throw new Error('项目数据响应无效，请检查 Yu+ 服务版本');
  }
  const data = {...vocabulary, ...raw};
  data.catalog = Array.isArray(raw.catalog) ? raw.catalog : raw.catalog?.objects || [];
  data.internal_types = (raw.internal_types || raw.catalog?.internal_types || []).map(t=>({...t,meaning:t.meaning || t.purpose,boundary:t.boundary || t.purpose}));
  for (const key of ['changes','decisions','review_checks','exports']) data[key] ||= [];
  for (const key of ['chat_monitors','monitor_runs']) data[key] = Array.isArray(raw[key]) ? raw[key] : [];
  data.project_activity ||= {};
  data.indexes = {
    objById:Object.fromEntries(data.objects.map(o=>[o.id,o])),
    revById:Object.fromEntries(data.object_revisions.map(r=>[r.id,r])),
    srcById:Object.fromEntries(data.sources.map(s=>[s.id,s])),
    svById:Object.fromEntries(data.source_versions.map(s=>[s.id,s])),
  };
  return data;
}

async function json(fetcher, url) {
  const response = await fetcher(url, {cache:'no-store'});
  if (!response.ok) throw new Error(`Yu+ 读取失败（HTTP ${response.status}）`);
  return response.json();
}

export async function loadView(projectId, fetcher=fetch) {
  const health = await json(fetcher, '/api/health');
  if (health.mode === 'demo') {
    // Explicit preview service only; live failures never fall back to samples.
    return (await import('./demo.js')).default;
  }
  if (health.mode !== 'live') throw new Error('当前地址不是可识别的 Yu+ 服务');
  return hydrateView(await json(fetcher, '/api/view' + (projectId ? '?project='+encodeURIComponent(projectId) : '')));
}
