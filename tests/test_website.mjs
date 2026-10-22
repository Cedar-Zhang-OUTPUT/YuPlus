import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const root=new URL('../website/',import.meta.url);
const prompt=readFileSync(new URL('install-prompt.txt',root),'utf8');
const html=readFileSync(new URL('index.html',root),'utf8');
const script=readFileSync(new URL('site.js',root),'utf8');
const guide=readFileSync(new URL('agent-install.md',root),'utf8');
function setup(clipboard) {
  const handlers=[];
  const field={value:prompt,focus(){this.focused=true},select(){this.selected=true},setSelectionRange(start,end){this.range=[start,end]}};
  const status={textContent:'',classList:{add(){},remove(){}}};
  const details={open:false};
  const document={querySelector:s=>({'#install-prompt':field,'#copy-status':status,'#full-prompt':details}[s]),querySelectorAll:()=>[1,2].map(()=>({addEventListener:(name,fn)=>handlers.push(fn)}))};
  vm.runInNewContext(script,{document,navigator:{clipboard},setTimeout:()=>1,clearTimeout(){}});
  return {handlers,field,status,details};
}
test('both entry points copy the short Agent guide prompt',async()=>{
  const copied=[];const app=setup({writeText:async text=>copied.push(text)});
  for(const handler of app.handlers)await handler();
  assert.deepEqual(copied,[prompt,prompt]);
  assert.match(app.status.textContent,/已复制短提示词/);
  assert.equal(app.details.open,false);
});
test('denied clipboard opens and selects short prompt without false success',async()=>{
  const app=setup({writeText:async()=>{throw Error('denied')}});await app.handlers[0]();
  assert.equal(app.details.open,true);assert.equal(app.field.focused,true);
  assert.deepEqual(app.field.range,[0,prompt.length]);assert.match(app.status.textContent,/手动复制/);
});
test('missing clipboard API offers manual copy',async()=>{
  const app=setup(undefined);await app.handlers[1]();
  assert.equal(app.details.open,true);assert.equal(app.field.selected,true);
  assert.match(app.status.textContent,/手动复制/);
});
test('embedded and downloadable short prompts point to the shipped public guide',()=>{
  const embedded=html.match(/<textarea[^>]+id="install-prompt"[^>]*>([\s\S]*?)<\/textarea>/)[1].replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&#x27;/g,"'").replace(/&quot;/g,'"').replace(/&amp;/g,'&');
  assert.equal(embedded,prompt);
  assert.ok([...prompt.trim()].length<=180);
  const urls=prompt.match(/https:\/\/[^\s]+/g);
  assert.deepEqual(urls,['https://cedar-zhang-output.github.io/YuPlus/agent-install.md']);
  assert.match(html,/href="\.\/agent-install\.md"/);
  assert.match(guide,/releases\/download\/v0\.3\.10\/YuPlus-v0\.3\.10\.tar\.gz/);
  assert.match(guide,/SHA256SUMS\.txt/);
  assert.match(guide,/6e13d32183edd8e56f48f2449b20d28f685e18d4f841dc3043e3aec9f2ded72a/);
  assert.match(guide,/先改 draft 再改 review/);
});

test('v0.3.10 guide preserves upgrade data and keeps monitoring opt-in',()=>{
  assert.match(prompt,/安装或升级到 Yu\+ v0\.3\.10/);
  assert.match(guide,/backup create --output NEW_BACKUP_DIR/);
  assert.match(guide,/schema_version: 3/);
  assert.match(guide,/0\.3\.10/);
  assert.match(guide,/安装或升级本身不创建监控/);
  assert.match(guide,/中文副本仅供用户审阅/);
  assert.doesNotMatch(html,/v0\.1/);
});
