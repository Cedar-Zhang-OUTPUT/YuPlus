export function documentUrl(value) {
  try {
    if (typeof value !== 'string' || /[\s\\]/.test(value)) return null;
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port ||
      !['feishu.cn','larksuite.com'].some(d => url.hostname === d || url.hostname.endsWith('.'+d)) ||
      !/^\/(docx|docs|wiki)\/[A-Za-z0-9_-]+\/?$/.test(url.pathname)) return null;
    return url.href;
  } catch { return null; }
}

export function exportHistory(data, projectId, fullTime) {
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);node.className = cls;
    if (text) node.textContent = text;
    return node;
  };
  const body = el('div','export-history');
  const records = (data.exports || []).filter(e => e.project_id === projectId && e.destination === 'feishu')
    .sort((a,b) => String(b.exported_at).localeCompare(String(a.exported_at)));
  if (!records.length) {
    body.append(el('p','muted','暂无导出记录'),el('p','small muted','Agent 完成飞书导出并保存记录后，会显示在这里。'));
    return body;
  }
  for (const record of records) {
    const row = el('article','relrow');const content = el('div','grow');
    const url = documentUrl(record.external_url);
    const title = el(url ? 'a' : 'span','export-document-link',record.external_title || '飞书文档');
    if (url) {title.href=url;title.target='_blank';title.rel='noopener noreferrer';}
    content.append(title,el('p','tiny muted',`导出于 ${fullTime(record.exported_at)}`));
    if (!url) content.append(el('p','tiny muted','文档链接不可用'));
    row.append(content);body.append(row);
  }
  return body;
}
