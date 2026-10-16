import DATA from './data/demo.js';
const id = new URLSearchParams(location.search).get('id');
const source = DATA.indexes.srcById[id];
const version = source && DATA.indexes.svById[source.latest_snapshot_id];
document.getElementById('title').textContent = source?.cached_title || (source ? '标题尚未取得' : '示例材料不存在');
document.title = (source?.cached_title || '示例原文') + ' · Yu+';
document.getElementById('meta').textContent = source ? `项目：${DATA.projects.find(p => p.id === source.project_id).name} · 来源：${source.id}` : '';
document.getElementById('body').textContent = version?.body_text || '该材料没有示例正文。';
