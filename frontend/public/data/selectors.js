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
