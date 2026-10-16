const canonical = value => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])]));
  return value;
};
const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
const evidence = refs => (refs || []).map(({ evidence_id, ...ref }) => ref);

export function compareBasisItems(beforeRevision, afterRevision, itemId) {
  const available = !!beforeRevision && !!afterRevision;
  const before = beforeRevision?.payload.items || [];
  const after = afterRevision?.payload.items || [];
  const oldItem = before.find(i => i.item_id === itemId);
  const newItem = after.find(i => i.item_id === itemId);
  // A removed ID may be replaced by several new items. Never infer a one-to-one
  // replacement from titles; show the object changes with their actual IDs.
  const wholeObject = !itemId || itemId === '*' || (!newItem && !!oldItem);
  const ids = wholeObject ? [...new Set([...before.map(i => i.item_id), ...after.map(i => i.item_id)])] : [itemId];
  return { wholeObject, removedReference: !!oldItem && !newItem, available,
    items: ids.map(id => {
      const old = before.find(i => i.item_id === id);
      const current = after.find(i => i.item_id === id);
      const fields = [...new Set([...Object.keys(old?.data || {}), ...Object.keys(current?.data || {})])].map(key => ({
        key, before: old?.data[key], after: current?.data[key], changed: available && !equal(old?.data[key], current?.data[key])
      }));
      const sourceChanged = available && !equal(evidence(old?.source_refs), evidence(current?.source_refs));
      const kindChanged = available && old?.epistemic_kind !== current?.epistemic_kind;
      const dependenciesChanged = available && !equal(old?.dependencies || [], current?.dependencies || []);
      return { id, before: old, after: current, fields, sourceChanged, kindChanged, dependenciesChanged,
        status: !available ? 'unknown' : !old ? (current ? 'added' : 'missing') : !current ? 'removed' :
          fields.some(f => f.changed) || sourceChanged || kindChanged || dependenciesChanged ? 'changed' : 'same' };
    }) };
}
