import test from 'node:test';
import assert from 'node:assert/strict';
import DATA from '../public/data/demo.js';
import {compareBasisItems} from '../public/data/basis-diff.js';
const rev = id => DATA.indexes.revById[id];

test('removed cited item compares object changes without inventing a replacement identity', () => {
  const diff = compareBasisItems(rev('rev_deliv_1'), rev('rev_deliv_2'), 'deliv_r1_film');
  assert.equal(diff.removedReference, true);
  assert.equal(diff.wholeObject, true);
  assert.equal(diff.items.find(i=>i.id==='deliv_r1_film').status,'removed');
  assert.equal(diff.items.find(i=>i.id==='deliv_r1_script').status,'added');
  assert.equal(diff.items.find(i=>i.id==='deliv_r1_film_deferred').status,'added');
  assert.equal(diff.items.find(i=>i.id==='deliv_r1_wall').status,'same');
});
test('same stable ID highlights only changed fields and source provenance', () => {
  const before = {payload:{items:[{item_id:'one', data:{title:'保留', count:0, optional:null}, source_refs:[{evidence_id:'a',source_version_id:'s1'}]}]}};
  const after = structuredClone(before);
  after.payload.items[0].data.count=2;
  delete after.payload.items[0].data.optional;
  after.payload.items[0].source_refs[0].source_version_id='s2';
  const [item] = compareBasisItems(before,after,'one').items;
  assert.equal(item.status,'changed');
  assert.deepEqual(item.fields.filter(f=>f.changed).map(f=>f.key),['count','optional']);
  assert.equal(item.sourceChanged,true);
  const renamedEvidence=structuredClone(before);
  renamedEvidence.payload.items[0].source_refs[0].evidence_id='b';
  assert.equal(compareBasisItems(before,renamedEvidence,'one').items[0].status,'same');
});
test('missing versions are unknown, not additions or deletions', () => {
  const diff=compareBasisItems(null,rev('rev_deliv_2'),'deliv_r1_script');
  assert.equal(diff.available,false);
  assert.equal(diff.items[0].status,'unknown');
  assert.equal(diff.items[0].fields.some(f=>f.changed),false);
});
