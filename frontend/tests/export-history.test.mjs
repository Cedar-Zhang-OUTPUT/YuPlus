import test from 'node:test';
import assert from 'node:assert/strict';
import {exportHistory,documentUrl} from '../public/data/export-history.js';
test('export history filters projects, sorts newest first and opens safe title links',()=>{
 const old=globalThis.document;
 globalThis.document={createElement:tag=>({tag,children:[],append(...nodes){this.children.push(...nodes)}})};
 const nodes=root=>[root,...root.children.flatMap(nodes)];
 try {
  const row=(id,time,url)=>({project_id:id,destination:'feishu',exported_at:time,external_title:'导出 '+time,external_url:url});
  const data={exports:[row('p','2026-10-21','https://a.feishu.cn/docx/A'),row('q','2026-10-25','https://a.feishu.cn/docx/Q'),row('p','2026-10-23','https://a.feishu.cn/docx/B'),row('p','2026-10-22','javascript:alert(1)')]};
  const all=nodes(exportHistory(data,'p',s=>s));
  assert.equal(all.filter(n=>n.tag==='article').length,3);
  const links=all.filter(n=>n.tag==='a');
  assert.deepEqual(links.map(n=>n.href),['https://a.feishu.cn/docx/B','https://a.feishu.cn/docx/A']);
  assert.equal(links[0].target,'_blank');assert.equal(links[0].rel,'noopener noreferrer');
  assert.ok(all.some(n=>n.textContent==='导出于 2026-10-23'));
  assert.ok(all.some(n=>n.textContent==='文档链接不可用'));
  assert.ok(nodes(exportHistory(data,'empty',s=>s)).some(n=>n.textContent==='暂无导出记录'));
 }finally{globalThis.document=old;}
 for(const bad of ['javascript:alert(1)','https://evil.com/docx/A','https://feishu.cn.evil.com/docx/A','https://a.feishu.cn/drive/folder/A','https://user@a.feishu.cn/docx/A'])assert.equal(documentUrl(bad),null);
});
