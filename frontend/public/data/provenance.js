import { basisStatus } from './selectors.js';
import { compareBasisItems } from './basis-diff.js';

// Walk recorded historical edges, never substitute current producer revisions.
export function expandBasis(data, bases) {
  const result=[], seen=new Set();
  function visit(edge, path) {
    const basis={...edge,object_id:edge.object_id || edge.producer_object_id,
      revision_id:edge.revision_id || edge.producer_revision_id,
      item_id:edge.item_id || edge.producer_item_id || '*'};
    const key=`${basis.object_id}:${basis.revision_id}:${basis.item_id}`;
    if (seen.has(key)) return;
    seen.add(key);result.push({...basis,path});
    const revision=data.indexes.revById[basis.revision_id];
    if (!revision || revision.object_id!==basis.object_id) return;
    const items=(revision.payload.items || []).filter(item=>basis.item_id==='*' || item.item_id===basis.item_id);
    for (const item of items) for (const child of item.dependencies || []) visit(child,[...path,{object_id:basis.object_id,item_id:item.item_id}]);
  }
  for (const basis of bases) visit(basis,[]);
  return result;
}

export function changedBasisDetails(data,bases) {
  const changed=expandBasis(data,bases).filter(b=>basisStatus(data,b)==='changed');
  const concrete=changed.filter(b=>{
    const object=data.indexes.objById[b.object_id];
    const diff=compareBasisItems(data.indexes.revById[b.revision_id],data.indexes.revById[object?.current_revision_id],b.item_id);
    return diff.available && (diff.structureFields.some(field=>field.changed) || diff.items.some(item=>item.status!=='same'));
  });
  return concrete.length ? concrete : changed;
}
