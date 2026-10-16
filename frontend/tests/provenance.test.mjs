import test from 'node:test';
import assert from 'node:assert/strict';
import {expandBasis,changedBasisDetails} from '../public/data/provenance.js';

test('indirect change resolves the actual upstream old/new item and historical source',()=>{
  const data={meta:{demo:false},basis_status_by_key:{'strategy:s1:plan':'changed','budget:b1:budget':'changed'},indexes:{
    objById:{strategy:{id:'strategy',current_revision_id:'s1'},budget:{id:'budget',current_revision_id:'b2'}},
    revById:{s1:{object_id:'strategy',payload:{items:[{item_id:'plan',data:{strategy:'按预算推进'},dependencies:[{producer_object_id:'budget',producer_revision_id:'b1',producer_item_id:'budget'}]}]}},
      b1:{object_id:'budget',payload:{items:[{item_id:'budget',data:{min_minor:'100000000'},source_refs:[{source_version_id:'original'}]}]}},
      b2:{object_id:'budget',payload:{items:[{item_id:'budget',data:{min_minor:'60000000'},source_refs:[{source_version_id:'decision'}]}]}}}}};
  const bases=[{object_id:'strategy',revision_id:'s1',item_id:'plan'}];
  assert.deepEqual(expandBasis(data,bases).map(b=>b.revision_id),['s1','b1']);
  assert.equal(changedBasisDetails(data,bases)[0].revision_id,'b1');
  assert.equal(changedBasisDetails(data,bases)[0].object_id,'budget');
  assert.equal(expandBasis(data,bases)[1].path[0].object_id,'strategy');
  // Missing history is retained as an unresolved edge, not replaced by head.
  delete data.indexes.revById.b1;
  assert.equal(expandBasis(data,bases)[1].revision_id,'b1');
});

test('whole-object provenance follows each item and terminates repeated/cyclic edges',()=>{
  const basis={object_id:'o',revision_id:'r',item_id:'*'};
  const data={indexes:{revById:{r:{object_id:'o',payload:{items:[{item_id:'a',dependencies:[basis]},{item_id:'b',dependencies:[{object_id:'x',revision_id:'old',item_id:'i'}]}]}}}}};
  assert.deepEqual(expandBasis(data,[basis]).map(b=>b.revision_id),['r','old']);
});

test('wildcard object title/order changes remain selectable beside item changes',()=>{
  const item={item_id:'i',data:{text:'same'}};
  const data={meta:{demo:false},basis_status_by_key:{'a:a1:*':'changed','b:b1:i':'changed'},indexes:{
    objById:{a:{current_revision_id:'a2'},b:{current_revision_id:'b2'}},revById:{
      a1:{object_id:'a',payload:{title:'旧标题',items:[item],item_order:['i']}},a2:{object_id:'a',payload:{title:'新标题',items:[item],item_order:['i']}},
      b1:{object_id:'b',payload:{items:[item]}},b2:{object_id:'b',payload:{items:[{item_id:'i',data:{text:'changed'}}]}}}}};
  const bases=[{object_id:'a',revision_id:'a1',item_id:'*'},{object_id:'b',revision_id:'b1',item_id:'i'}];
  assert.deepEqual(changedBasisDetails(data,bases).map(b=>b.object_id),['a','b']);
});
