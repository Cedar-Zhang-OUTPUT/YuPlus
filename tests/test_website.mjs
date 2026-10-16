import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const root=new URL('../website/',import.meta.url);
const prompt=readFileSync(new URL('install-prompt.txt',root),'utf8');
const html=readFileSync(new URL('index.html',root),'utf8');
const script=readFileSync(new URL('site.js',root),'utf8');
function setup(clipboard) {
  const handlers=[];
  const field={value:prompt,focus(){this.focused=true},select(){this.selected=true},setSelectionRange(start,end){this.range=[start,end]}};
  const status={textContent:'',classList:{add(){},remove(){}}};
  const details={open:false};
  const document={querySelector:s=>({'#install-prompt':field,'#copy-status':status,'#full-prompt':details}[s]),querySelectorAll:()=>[1,2].map(()=>({addEventListener:(name,fn)=>handlers.push(fn)}))};
  vm.runInNewContext(script,{document,navigator:{clipboard},setTimeout:()=>1,clearTimeout(){}});
  return {handlers,field,status,details};
}
test('both entry points copy the entire pinned release prompt',async()=>{
  const copied=[];const app=setup({writeText:async text=>copied.push(text)});
  for(const handler of app.handlers)await handler();
  assert.deepEqual(copied,[prompt,prompt]);
  assert.match(app.status.textContent,/已复制完整/);
  assert.equal(app.details.open,false);
});
test('denied clipboard opens and selects full prompt without false success',async()=>{
  const app=setup({writeText:async()=>{throw Error('denied')}});await app.handlers[0]();
  assert.equal(app.details.open,true);assert.equal(app.field.focused,true);
  assert.deepEqual(app.field.range,[0,prompt.length]);assert.match(app.status.textContent,/手动复制/);
});
test('embedded and downloadable prompts match and release links are fixed',()=>{
  const embedded=html.match(/<textarea[^>]+id="install-prompt"[^>]*>([\s\S]*?)<\/textarea>/)[1].replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&#x27;/g,"'").replace(/&quot;/g,'"').replace(/&amp;/g,'&');
  assert.equal(embedded,prompt);
  assert.match(prompt,/releases\/download\/v0\.1\/YuPlus-v0\.1\.tar\.gz/);
  assert.match(prompt,/SHA256SUMS\.txt/);
  assert.match(prompt,/先改 draft 再更新相关 review/);
});
