/** Compare the exact cited item, not unrelated changes in the same object.
 * Missing evidence is unknown rather than falsely "up to date".
 * A future API adapter should use review.prepare's authoritative affected blocks.
 */
const canonical = (value) => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])]));
  return value;
};
const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
export function basisStatus(data, basis) {
  if (data.meta?.demo === false) {
    const key = `${basis.object_id}:${basis.revision_id}:${basis.item_id || '*'}`;
    const status = data.basis_status_by_key?.[key];
    return ['same','changed','unknown'].includes(status) ? status : 'unknown';
  }
  const object = data.indexes.objById[basis.object_id];
  const old = data.indexes.revById[basis.revision_id];
  const current = data.indexes.revById[object?.current_revision_id];
  if (!object || !old || !current || old.object_id !== object.id) return 'unknown';
  if (!basis.item_id) return equal(old.payload, current.payload) ? 'same' : 'changed';
  const before = old.payload.items?.find(i => i.item_id === basis.item_id);
  const after = current.payload.items?.find(i => i.item_id === basis.item_id);
  if (!before) return 'unknown';
  if (!after) return 'changed';
  // Evidence identities may be regenerated when an unchanged citation is carried forward.
  const content = (item) => ({ ...item, source_refs: (item.source_refs || []).map(({ evidence_id, ...ref }) => ref) });
  return equal(content(before), content(after)) ? 'same' : 'changed';
}

// Canonical CLI statuses and legacy demo labels share one presentation mapping.
export function qaState(status) {
  if (status === 'answered' || status === '已答复') return {label:'已答复',hue:'green',answered:true};
  if (status === 'closed') return {label:'已关闭',hue:'gray',answered:false};
  if (status === '不适用') return {label:'不适用',hue:'gray',answered:false};
  if (status === 'open' || status === '待答复') return {label:'待答复',hue:'orange',answered:false};
  return {label:status || '未记录状态',hue:'gray',answered:false};
}

// Open discussion is distinct from a customer question awaiting an answer.
export function openQuestionState(status) {
  const states = {open:['待讨论','orange'], exploring:['探索中','purple'], resolved:['已有结论','green'], deferred:['暂缓','gray'], closed:['已关闭','gray']};
  const [label, hue] = states[status] || [status || '未记录状态','gray'];
  return {label, hue};
}
