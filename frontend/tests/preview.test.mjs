import test from 'node:test';
import assert from 'node:assert/strict';
import { request } from 'node:http';
import { once } from 'node:events';
import DATA from '../public/data/demo.js';
import { basisStatus } from '../public/data/selectors.js';
import { createPreviewServer } from '../server.mjs';

test('D18 change affects only cited film item, not unchanged wall item', () => {
  const base = { object_id:'obj_deliv', revision_id:'rev_deliv_1' };
  assert.equal(basisStatus(DATA, {...base, item_id:'deliv_r1_film'}), 'changed');
  assert.equal(basisStatus(DATA, {...base, item_id:'deliv_r1_wall'}), 'same');
  assert.equal(basisStatus(DATA, {...base, item_id:'nonexistent'}), 'unknown');
});
test('missing revision cannot be reported as current', () => {
  assert.equal(basisStatus(DATA, {object_id:'obj_deliv', revision_id:'missing',item_id:'deliv_r1_film'}), 'unknown');
});
test('mock dataset keeps project, source, and review lineage identities intact', () => {
  assert.equal(DATA.catalog.length,23);
  assert.equal(DATA.objects.some(o => o.type_key === 'qa_view'),false);
  for (const o of DATA.objects) {
    assert.ok(DATA.projects.find(p => p.id === o.project_id));
    if(o.current_revision_id) assert.equal(DATA.indexes.revById[o.current_revision_id].object_id,o.id);
  }
  for (const r of DATA.object_revisions) {
    const project = DATA.indexes.objById[r.object_id].project_id;
    for (const item of r.payload.items || []) {
      for (const ref of item.source_refs || []) {
        const sv = DATA.indexes.svById[ref.source_version_id];
        assert.ok(sv,ref.source_version_id);
        assert.equal(DATA.indexes.srcById[sv.source_id].project_id,project);
      }
    }
    for(const lineage of Object.values(r.block_lineage || {})) for(const basis of lineage.basis || []) {
      const object = DATA.indexes.objById[basis.object_id];
      assert.equal(object.project_id,project);
      assert.equal(object.layer,'draft');
      assert.notEqual(basisStatus(DATA,basis),'unknown',JSON.stringify(basis));
    }
  }
  assert.equal(DATA.review_checks.length,0);
  assert.equal(DATA.exports.length,0);
  for(const source of DATA.sources) {
    assert.ok(!source.remote_observation);
    if(source.canonical_url) assert.ok(source.canonical_url.startsWith('./source.html?id='));
  }
});

test('preview serves public assets only and refuses write methods', async () => {
  const server = createPreviewServer();
  server.listen(0,'127.0.0.1'); await once(server,'listening');
  const port = server.address().port;
  const call = (path,method='GET') => new Promise((resolve,reject) => {
    const req = request({host:'127.0.0.1',port,path,method}, res => {
      let body='';res.setEncoding('utf8');res.on('data',c => body+=c);res.on('end',() => resolve({status:res.statusCode,body,headers:res.headers}));
    });req.on('error',reject);req.end();
  });
  try {
    assert.match((await call('/')).body,/<main id="stage">/);
    assert.equal((await call('/data/demo.js')).status,200);
    assert.equal((await call('/styles/tokens.css')).status,200);
    assert.equal((await call('/source.html?id=src_brief')).status,200);
    assert.equal((await call('/','HEAD')).body,'');
    for (const method of ['POST','PATCH','DELETE']) assert.equal((await call('/',method)).status,405);
    assert.equal((await call('/server.mjs')).status,404);
    assert.equal((await call('/%2e%2e%2f%2e%2e%2fREADME.md')).status,403);
    assert.equal((await call('/data/')).status,404);
    assert.equal((await call('/%ZZ')).status,400);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
