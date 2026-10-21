import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const app = await readFile(new URL('../public/app.js', import.meta.url), 'utf8');
const renderer = app.slice(app.indexOf('let localFileCapabilities'), app.indexOf('function kv('));
const asset = {asset_id:'image', storage:'copy', availability:'available', display_name:'现场照片1.jpg',
  url:'/api/assets?project=p&version=v&asset=image', download_url:'/api/assets?project=p&version=v&asset=image&download=1'};
function setup(capability) {
  const calls=[];
  const el = () => ({children:[], classList:{add(){}}, setAttribute(){}, append(...nodes){this.children.push(...nodes);}});
  const context=vm.createContext({DATA:{meta:{demo:false}}, S:{route:{pid:'p'}}, el,
    chipBtn:(textContent,onclick)=>({...el(),textContent,onclick}),
    fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>options?{ok:true}:capability};}});
  vm.runInContext(renderer,context);
  return {context,calls,el};
}
async function render(env, item=asset) {
  const container=env.el();env.context.addFileAction(container,{id:'v'},item);
  await new Promise(setImmediate); return container.children;
}

test('pool attachments offer original-name download instead of Finder even with a stale capability',async()=>{
  const env=setup({supported:true,files:[{versionId:'v',assetId:'image'}]});
  const nodes=await render(env);
  assert.equal(nodes[0].textContent,'下载');
  assert.equal(nodes[0].href,asset.download_url);
  assert.equal(nodes[0].download,'现场照片1.jpg');
  assert.equal(env.calls.length,0);
});
test('external originals offer Finder only when server confirms their identity',async()=>{
  const env=setup({supported:true,files:[{versionId:'v',assetId:'image'}]});
  const nodes=await render(env,{...asset,storage:'external'});
  const finder=nodes.find(node=>node.textContent==='在 Finder 中显示');
  assert.ok(finder);
  await finder.onclick();
  const payload=JSON.parse(env.calls[1].options.body);
  assert.deepEqual(payload,{projectId:'p',versionId:'v',assetId:'image'});
});
test('restored external files and unsupported platforms offer download',async()=>{
  for(const capability of [{supported:true,files:[]},{supported:false,files:[]}]){
    const nodes=await render(setup(capability),{...asset,storage:'external'});
    assert.equal(nodes.length,1);
    assert.equal(nodes[0].textContent,'下载');
    assert.equal(nodes[0].href,asset.download_url);
  }
});
test('unavailable snapshots do not promise download or Finder',async()=>{
  for(const availability of ['missing','changed','unavailable']){
    assert.equal((await render(setup({supported:true,files:[]}),{...asset,availability})).length,0);
  }
});
