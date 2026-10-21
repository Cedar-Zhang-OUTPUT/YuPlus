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
  assert.equal(DATA.catalog.length,24);
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

test('design preview has content for every business object and every review kind', () => {
  const objects = DATA.objects.filter(o=>o.project_id==='prj_city');
  for (const type of DATA.catalog) {
    const object = objects.find(o=>o.type_key===type.type_key);
    assert.ok(object, type.name);
    const revision = DATA.indexes.revById[object.current_revision_id];
    assert.ok(revision?.payload.items.length>0, type.name);
    assert.deepEqual(new Set(revision.payload.item_order),new Set(revision.payload.items.map(i=>i.item_id)));
  }
  for (const kind of DATA.REVIEW_KINDS.filter(k=>k.persistable)) {
    const object = objects.find(o=>o.type_key===kind.type_key);
    assert.ok(DATA.indexes.revById[object.current_revision_id]?.payload.blocks.length>0,kind.name);
  }
  for (const list of [DATA.objects,DATA.object_revisions,DATA.sources,DATA.source_versions,DATA.changes]) {
    assert.equal(new Set(list.map(x=>x.id)).size,list.length,'fixture identities must remain unique');
  }
  for (const revision of DATA.object_revisions.filter(r=>r.change_id.startsWith('chg_design_'))) {
    assert.ok(DATA.changes.some(c=>c.id===revision.change_id));
    for (const item of revision.payload.items) for (const id of item.data.related_object_ids || []) {
      assert.equal(DATA.indexes.objById[id]?.project_id,'prj_city',id);
    }
  }
});

test('minute examples preserve existing cited timeline items and have readable sources', () => {
  const current = DATA.indexes.revById[DATA.indexes.objById.obj_timeline.current_revision_id];
  assert.ok(current.payload.items.some(i=>i.data.date?.includes('T')));
  assert.ok(current.payload.items.some(i=>i.data.start?.includes('T')));
  for (const item of DATA.indexes.revById.rev_timeline_1.payload.items) {
    assert.equal(basisStatus(DATA,{object_id:'obj_timeline',revision_id:'rev_timeline_1',item_id:item.item_id}),'same');
  }
  for (const source of DATA.sources.filter(s=>s.id.startsWith('src_design_'))) {
    assert.ok(DATA.indexes.svById[source.latest_snapshot_id].body_text.length>100);
  }
});
