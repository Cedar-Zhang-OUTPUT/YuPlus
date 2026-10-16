import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { createPreviewServer } from '../server.mjs';
import { createLocalFiles } from '../local-files.mjs';

test('Finder bridge reveals registered snapshots and rejects foreign origins and arbitrary paths', async () => {
  const root = await mkdtemp(join(tmpdir(),'yu-finder-test-'));
  const revealed = [];
  const server = createPreviewServer({localFiles:{platform:'darwin',cacheRoot:join(root,'cache'),reveal:async path=>revealed.push(path)}});
  server.listen(0,'127.0.0.1'); await once(server,'listening');
  const origin = `http://127.0.0.1:${server.address().port}`;
  const payload = {versionId:'sv_brief_1',assetId:'a_body'};
  const post = (data=payload, headers={}) => fetch(origin+'/api/local-files/reveal',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json',...headers},body:JSON.stringify(data)});
  try {
    const capabilities = await (await fetch(origin+'/api/local-files')).json();
    assert.equal(capabilities.supported,true);
    assert.ok(capabilities.files.some(f=>f.versionId==='sv_brief_1'&&f.assetId==='a_body'));
    assert.ok(!capabilities.files.some(f=>f.versionId==='sv_photos_1'||f.versionId==='sv_deck_1'));
    assert.ok(capabilities.files.every(f=>!('path' in f)));
    assert.equal((await post()).status,200);
    assert.equal(revealed.length,1);
    assert.match(await readFile(revealed[0],'utf8'),/项目背景/);
    assert.equal((await post(payload,{Origin:'https://unrelated.example'})).status,403);
    assert.equal((await post(payload,{Origin:''})).status,403);
    assert.equal((await post(payload,{'Content-Type':'text/plain'})).status,403);
    assert.equal((await post({...payload,path:'/etc/passwd'})).status,400);
    assert.equal((await post({versionId:'../../etc',assetId:'passwd'})).status,404);
    assert.equal((await fetch(origin+'/api/local-files/reveal')).status,405);
    assert.equal((await fetch(origin+'/.preview/source-files/sv_brief_1/test.md')).status,404);
    assert.equal(revealed.length,1);
    const path = revealed[0];
    await rm(path);
    assert.equal((await post()).status,404);
    const outside = join(root,'outside.txt'); await writeFile(outside,'outside');
    await symlink(outside,path);
    assert.equal((await post()).status,404);
    assert.equal(revealed.length,1);
  } finally {
    await new Promise(resolve=>server.close(resolve));
    await rm(root,{recursive:true,force:true});
  }
});

test('non-macOS environments advertise no Finder action', async () => {
  let invoked=false;
  const files=createLocalFiles({platform:'linux',reveal:async()=>{invoked=true;}});
  assert.deepEqual(await files.list(),{supported:false,files:[]});
  assert.equal((await files.reveal('sv_brief_1','a_body')).status,501);
  assert.equal(invoked,false);
});
