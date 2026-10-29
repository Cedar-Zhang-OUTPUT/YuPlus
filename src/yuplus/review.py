"""Author complete review documents from immutable draft evidence.

The runner owns the transaction. This module validates every document before
writing any revision; it never invents text, edits draft, or calls a model.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re

from .core import (YuError, canonical, fingerprint, get_object, insert, is_fresh,
                   load_revision, new_id, now, resolve_dependency, write_revision)

_REVIEW_TYPES = {'debrief', 'advancement', 'creative_review', 'creative_plan'}
_STRUCTURE = '__document__'


def _error(code, message, **details):
    raise YuError(code, message, details=[details] if details else [],
                  retryable=code in {'BASE_REVISION_CONFLICT', 'DRAFT_BASIS_CHANGED'},
                  next_action='重新读取 draft 和 review.prepare，按当前依据提交。')


def _unique(values, label):
    if len(values) != len(set(values)):
        _error('INVALID_INPUT', f'{label} 不可重复。')


def _scope(ctx, target):
    typ, scope = target['type_key'], target['scope_key']
    if typ not in _REVIEW_TYPES:
        _error('INVALID_SCOPE', '该类型不是可发布的 review；Q&A 请读取 draft。')
    if typ == 'creative_plan':
        if not scope.startswith('proposal:'):
            _error('INVALID_SCOPE', '创意方案需要 proposal:<创意方案条目ID> 范围。')
        obj = ctx.db.execute("SELECT current_revision_id FROM objects WHERE project_id=? AND type_key='creative_proposals' AND archived_at IS NULL", (ctx.project_id,)).fetchone()
        if not obj or scope[9:] not in _items(load_revision(ctx.db, ctx.project_id, obj[0])):
            _error('INVALID_SCOPE', '创意方案需先保存对应 draft 条目。')
        return
    if scope == 'project':
        return
    round_only = re.fullmatch(r'round:([A-Za-z][A-Za-z0-9_-]*)', scope)
    if not round_only:
        _error('INVALID_SCOPE', '成果范围必须是 project 或有效轮次。', scope_key=scope)
    round_key = round_only.group(1)
    delivery = ctx.db.execute("SELECT current_revision_id FROM objects WHERE project_id=? AND type_key='deliverables' AND layer='draft' AND archived_at IS NULL", (ctx.project_id,)).fetchone()
    if not delivery or not any(i['data'].get('round_key') == round_key for i in _items(load_revision(ctx.db, ctx.project_id, delivery[0])).values()):
        _error('INVALID_SCOPE', '成果轮次未在同项目交付条目中定义。', round_key=round_key)


def _target(ctx, target, allow_stale_scope=False):
    if target.get('object_id'):
        obj = get_object(ctx.db, ctx.project_id, target['object_id'])
        if (obj['layer'], obj['type_key'], obj['scope_key']) != ('review', target['type_key'], target['scope_key']):
            _error('INVALID_SCOPE', '成果身份与类型或范围不一致。', object_id=obj['id'])
    else:
        row = ctx.db.execute("SELECT * FROM objects WHERE project_id=? AND layer='review' AND type_key=? AND scope_key=?", (ctx.project_id, target['type_key'], target['scope_key'])).fetchone()
        obj = dict(row) if row else None
    if not (allow_stale_scope and obj):
        _scope(ctx, target)
    if obj and obj.get('archived_at'):
        _error('INVALID_SCOPE', '已归档成果不能以新身份绕过历史。', object_id=obj['id'])
    return obj


def _items(revision):
    return {item['item_id']: item for item in revision['payload'].get('items', [])}


def _deps(revision, item):
    return revision.get('dependencies', {}).get(item, [])


def _closure(ctx, deps):
    """Include upstream selectors without replacing their recorded revisions."""
    out, seen = [], set()
    def visit(dep):
        key = (dep['object_id'], dep['revision_id'], dep['item_id'])
        if key in seen:
            return
        seen.add(key)
        out.append(dep)
        rev = load_revision(ctx.db, ctx.project_id, dep['revision_id'])
        item_ids = _items(rev) if dep['item_id'] == '*' else [dep['item_id']]
        for item in item_ids:
            for upstream in _deps(rev, item):
                visit(upstream)
    for dep in deps:
        visit(dep)
    return out


def _changes(ctx):
    return [dict(row) for row in ctx.db.execute("SELECT * FROM changes WHERE project_id=? AND command IN ('draft.apply','draft.delete') AND effect='changed' ORDER BY seq", (ctx.project_id,))]


def _intersects(ref, dep):
    return ref.get('object_id') == dep['object_id'] and (dep['item_id'] == '*' or '*' in ref.get('item_ids', []) or dep['item_id'] in ref.get('item_ids', []))


def _selector_changed(ctx, ref, dep):
    """An object-wide title/order edit is not a change to every child item."""
    if not _intersects(ref, dep):
        return False
    def value(revision_id):
        if not revision_id:
            return None
        try:
            return fingerprint(ctx.db, ctx.project_id, revision_id, dep['item_id'])
        except YuError as exc:
            if exc.code == 'INVALID_ITEM_REFERENCE':
                return None
            raise
    return value(ref.get('before_revision_id')) != value(ref.get('revision_id'))


def _adopted(ctx, deps, *, effective_current=False):
    """Everything already represented by each selected version is consumed.

    This is selector-specific, so an unrelated sibling revision is not a cause
    for rewriting the selected paragraph.
    """
    closure = _closure(ctx, deps)
    versions = {}
    for dep in closure:
        revision_id = dep['revision_id']
        # A recorded upstream selector may point to an older version whose
        # value became current again after a reversion. At publication the
        # intervening history is already known, not a future rewrite cause.
        if effective_current and is_fresh(ctx.db, ctx.project_id, revision_id, dep['item_id']):
            revision_id = get_object(ctx.db, ctx.project_id, dep['object_id'])['current_revision_id']
        versions[(dep['object_id'], dep['revision_id'])] = load_revision(ctx.db, ctx.project_id, revision_id)['version']
    adopted = set()
    for change in _changes(ctx):
        for ref in json.loads(change['changed_refs_json']):
            for dep in closure:
                if not ref.get('revision_id') or not _selector_changed(ctx, ref, dep):
                    continue
                rev = load_revision(ctx.db, ctx.project_id, ref['revision_id'])
                if rev['version'] <= versions[(dep['object_id'], dep['revision_id'])]:
                    adopted.add(change['id'])
    return adopted


def _guide_matches(ctx, ref, oid, block, read_basis, structural=False):
    obj = get_object(ctx.db, ctx.project_id, ref['object_id'])
    if obj['type_key'] != 'expression_guide' or obj['scope_key'] != 'review:' + oid:
        return False
    if read_basis.get(obj['id']) != obj['current_revision_id']:
        return False
    revision = load_revision(ctx.db, ctx.project_id, ref['revision_id'])
    chosen = _items(revision)
    selected = chosen if '*' in ref.get('item_ids', []) else ref.get('item_ids', [])
    for item_id in selected:
        item = chosen.get(item_id)
        if not item:
            continue
        data = item['data']
        blocks = data.get('block_ids', [])
        matches = '*' in blocks if structural else ('*' in blocks or block in blocks)
        if data.get('review_object_id') == oid and matches and _selector_changed(ctx, ref, {'object_id': obj['id'], 'item_id': item_id}) and is_fresh(ctx.db, ctx.project_id, ref['revision_id'], item_id):
            return True
    return False


def _ref_effective(ctx, ref, dep):
    """A superseded intermediate fact must not authorize the current wording."""
    old = load_revision(ctx.db, ctx.project_id, ref['revision_id'])
    obj = get_object(ctx.db, ctx.project_id, ref['object_id'])
    current = load_revision(ctx.db, ctx.project_id, obj['current_revision_id'])
    selector = dep['item_id']
    if selector != '*' and selector not in _items(old):
        return selector not in _items(current)  # A genuine removal remains relevant.
    return is_fresh(ctx.db, ctx.project_id, old['id'], selector)


def _causes(ctx, ids, *, oid, block, old_deps, new_deps, lineage, read_basis, first_seq=None, structural=False):
    _unique(ids, 'cause_change_ids')
    if not ids:
        _error('DRAFT_CHANGE_REQUIRED', '更新 review 前必须先修改相关 draft。', block_id=block)
    consumed = set(lineage.get('applied_cause_ids', []))
    consumed.update(_adopted(ctx, old_deps))
    selectors = _closure(ctx, old_deps + new_deps)
    authored_seq = None
    if lineage.get('last_authored_revision_id'):
        authored = ctx.db.execute('SELECT c.seq FROM object_revisions r JOIN changes c ON c.project_id=r.project_id AND c.id=r.change_id WHERE r.project_id=? AND r.id=?', (ctx.project_id, lineage['last_authored_revision_id'])).fetchone()
        authored_seq = authored[0] if authored else None
    for cid in ids:
        change = ctx.db.execute('SELECT * FROM changes WHERE project_id=? AND id=?', (ctx.project_id, cid)).fetchone()
        if not change or change['command'] not in {'draft.apply','draft.delete'} or change['effect'] != 'changed':
            _error('DRAFT_CHANGE_REQUIRED', 'review 的原因必须是同项目真实 draft 修改。', change_id=cid, block_id=block)
        if cid in consumed or (authored_seq is not None and change['seq'] <= authored_seq) or (first_seq is not None and change['seq'] <= first_seq):
            _error('CAUSE_ALREADY_APPLIED', '该 draft 变更已经体现在此段落中。', change_id=cid, block_id=block)
        matched = False
        for ref in json.loads(change['changed_refs_json']):
            if not ref.get('object_id') or not ref.get('revision_id'):
                continue
            obj = get_object(ctx.db, ctx.project_id, ref['object_id'])
            if obj['type_key'] == 'expression_guide':
                matched |= _guide_matches(ctx, ref, oid, block, read_basis, structural)
            elif not structural:
                matched |= any(_selector_changed(ctx, ref, dep) and _ref_effective(ctx, ref, dep) for dep in selectors)
        if not matched:
            _error('DRAFT_CHANGE_REQUIRED', '该 draft 修改与段落无关或已被后续修改替代。', change_id=cid, block_id=block)
    return consumed | set(ids) | _adopted(ctx, new_deps, effective_current=True)


def _read_basis(ctx, basis):
    _unique([item['object_id'] for item in basis], 'read_basis 对象')
    result = {}
    for n, item in enumerate(basis):
        obj = get_object(ctx.db, ctx.project_id, item['object_id'])
        if obj['layer'] != 'draft' or obj['current_revision_id'] != item['revision_id']:
            _error('DRAFT_BASIS_CHANGED', 'draft 依据已变化，请重新读取。', path=f'/read_basis/{n}', object_id=obj['id'], expected=item['revision_id'], actual=obj['current_revision_id'])
        result[obj['id']] = item['revision_id']
    return result


def _fresh(ctx, dep):
    return is_fresh(ctx.db, ctx.project_id, dep['revision_id'], dep['item_id'])


def _dependency_basis(ctx, deps, basis, block):
    _unique([d['dependency_id'] for d in deps], 'dependency_id')
    result = []
    if not deps:
        _error('DRAFT_CHANGE_REQUIRED', '每段成果至少需要一个 draft 依据。', block_id=block)
    for dep in deps:
        if basis.get(dep['object_id']) != dep['revision_id']:
            _error('DRAFT_BASIS_CHANGED', '段落依据未列入本次 read_basis。', object_id=dep['object_id'], revision_id=dep['revision_id'], block_id=block)
        resolved = resolve_dependency(ctx, dep)
        if dep['item_id'] == '*' and not _items(load_revision(ctx.db, ctx.project_id, dep['revision_id'])):
            _error('DRAFT_CHANGE_REQUIRED', '空 draft 对象不能作为成果段落的依据。', object_id=dep['object_id'], block_id=block)
        result.append(resolved)
    return result


def _comparable_deps(deps):
    return sorted(({k: v for k, v in d.items() if k != 'revision_id'} for d in deps), key=lambda d: d['dependency_id'])


def _first_publication_seq(ctx, oid):
    row = ctx.db.execute('SELECT c.seq FROM object_revisions r JOIN changes c ON c.project_id=r.project_id AND c.id=r.change_id WHERE r.project_id=? AND r.object_id=? ORDER BY r.version LIMIT 1', (ctx.project_id, oid)).fetchone()
    return row[0] if row else None


def _plan_document(ctx, doc):
    obj = _target(ctx, doc['target'], allow_stale_scope=True)
    current = obj['current_revision_id'] if obj else None
    if current != doc['base_revision']:
        _error('BASE_REVISION_CONFLICT', 'review 当前版本与 base_revision 不一致。', expected=doc['base_revision'], actual=current)
    oid = obj['id'] if obj else new_id('obj')
    old = load_revision(ctx.db, ctx.project_id, current) if current else None
    basis = _read_basis(ctx, doc['read_basis'])
    old_blocks = {b['block_id']: b for b in old['payload']['blocks']} if old else {}
    blocks, dependencies = deepcopy(old_blocks), deepcopy(old['dependencies']) if old else {}
    lineage = deepcopy(old['lineage']) if old else {}
    set_ids = [b['block_id'] for b in doc.get('set_blocks', [])]
    remove_ids = [b['block_id'] for b in doc.get('remove_blocks', [])]
    _unique(set_ids, 'set_blocks.block_id')
    _unique(remove_ids, 'remove_blocks.block_id')
    if set(set_ids) & set(remove_ids):
        _error('INVALID_INPUT', '同一段落不能同时修改与删除。')
    changed, removed, cause_ids = [], [], set()
    for block in doc.get('set_blocks', []):
        bid = block['block_id']
        if bid == _STRUCTURE:
            _error('INVALID_INPUT', '段落 ID 使用了内部保留值。')
        if not block['markdown'].strip():
            _error('INVALID_INPUT', '段落内容不能为空。', block_id=bid)
        deps = _dependency_basis(ctx, block['dependencies'], basis, bid)
        body = {'block_id': bid, 'markdown': block['markdown']}
        if old_blocks.get(bid) == body and _comparable_deps(dependencies.get(bid, [])) == _comparable_deps(deps):
            continue
        previous = lineage.get(bid, {})
        if old:
            consumed = _causes(ctx, block['cause_change_ids'], oid=oid, block=bid,
                               old_deps=previous.get('basis', dependencies.get(bid, [])), new_deps=deps,
                               lineage=previous, read_basis=basis,
                               first_seq=_first_publication_seq(ctx, oid) if bid not in lineage and bid not in old_blocks else None)
        else:
            if block['cause_change_ids']:
                _causes(ctx, block['cause_change_ids'], oid=oid, block=bid, old_deps=[], new_deps=deps, lineage={}, read_basis=basis)
            consumed = set(block['cause_change_ids']) | _adopted(ctx, deps, effective_current=True)
        cause_ids.update(block['cause_change_ids'])
        blocks[bid], dependencies[bid] = body, deps
        lineage[bid] = {'last_authored_revision_id': None, 'applied_cause_ids': sorted(consumed), 'basis': deps, 'deleted': False}
        changed.append(bid)
    for removal in doc.get('remove_blocks', []):
        bid = removal['block_id']
        if bid not in old_blocks:
            _error('INVALID_ITEM_REFERENCE', '删除的 review 段落不存在。', block_id=bid)
        previous = lineage.get(bid, {})
        consumed = _causes(ctx, removal['cause_change_ids'], oid=oid, block=bid,
                           old_deps=dependencies.get(bid, []), new_deps=[], lineage=previous, read_basis=basis)
        lineage[bid] = {'last_authored_revision_id': None, 'applied_cause_ids': sorted(consumed), 'basis': dependencies.get(bid, []), 'deleted': True}
        del blocks[bid]
        dependencies.pop(bid, None)
        removed.append(bid)
        cause_ids.update(removal['cause_change_ids'])
    if not blocks and not old:
        _error('INVALID_INPUT', '初次成果至少需要一个有依据的段落。')
    if blocks:
        _scope(ctx, doc['target'])
    for bid, deps in dependencies.items():
        for dep in deps:
            if not _fresh(ctx, dep):
                _error('STALE_DEPENDENCY', '此成果仍有段落依赖失效的 draft。', block_id=bid, object_id=dep['object_id'], item_id=dep['item_id'])
    old_order = old['payload']['block_order'] if old else []
    automatic_order = [bid for bid in old_order if bid in blocks] + [bid for bid in set_ids if bid not in old_order]
    order = doc.get('block_order', automatic_order)
    _unique(order, 'block_order')
    if set(order) != set(blocks):
        _error('INVALID_INPUT', 'block_order 必须完整列出所有最终段落。')
    outline_version=doc.get('outline_version',old['payload'].get('outline_version') if old else None)
    if blocks and (outline_version==2 or doc['target']['type_key']=='creative_plan'):
        from .collaboration import OUTLINES
        headings=re.findall(r'^##\s+(.+?)\s*$', '\n'.join(blocks[b]['markdown'] for b in order),re.M)
        if headings!=OUTLINES[doc['target']['type_key']]:
            _error('INVALID_REVIEW_STRUCTURE','策划文档栏目与约定结构不一致。',expected=OUTLINES[doc['target']['type_key']],actual=headings)
    old_title = old['payload']['title'] if old else doc['target']['type_key']
    title = doc.get('title', old_title)
    if not title.strip():
        _error('INVALID_INPUT', '成果标题不能为空。')
    structure_changed = old and (title != old_title or order != automatic_order)
    if structure_changed:
        previous = lineage.get(_STRUCTURE, {})
        consumed = _causes(ctx, doc['structure_cause_change_ids'], oid=oid, block='*', old_deps=[], new_deps=[],
                           lineage=previous, read_basis=basis, structural=True,
                           first_seq=_first_publication_seq(ctx, oid) if not previous else None)
        lineage[_STRUCTURE] = {'last_authored_revision_id': None, 'applied_cause_ids': sorted(consumed)}
        cause_ids.update(doc['structure_cause_change_ids'])
    payload = {'title': title, 'blocks': [blocks[bid] for bid in order], 'block_order': order}
    if outline_version==2: payload['outline_version']=2
    return {'object': obj, 'object_id': oid, 'target': doc['target'], 'old': old,
            'payload': payload, 'dependencies': dependencies, 'lineage': lineage,
            'changed_blocks': changed, 'removed_blocks': removed, 'causes': cause_ids,
            'basis': doc['read_basis'], 'changed': bool(not old or changed or removed or structure_changed)}


def publish_review(ctx, request):
    """Validate all patches; persist complete causally constrained documents."""
    identities = [(d['target']['type_key'], d['target']['scope_key']) for d in request['documents']]
    _unique(identities, 'documents 成果身份')
    plans = [_plan_document(ctx, doc) for doc in request['documents']]
    output = []
    for plan in plans:
        if plan['changed']:
            if not plan['object']:
                insert(ctx.db, 'objects', project_id=ctx.project_id, id=plan['object_id'], layer='review',
                       type_key=plan['target']['type_key'], scope_key=plan['target']['scope_key'], created_at=now())
            result = write_revision(ctx, plan['object_id'], plan['payload'], dependencies=plan['dependencies'],
                                    lineage=plan['lineage'], changed_items=plan['changed_blocks'] + plan['removed_blocks'])
            for cid in sorted(plan['causes']):
                if cid not in ctx.causal_change_ids:
                    ctx.causal_change_ids.append(cid)
        else:
            result = {'object_id': plan['object_id'], 'revision_id': plan['old']['id'], 'version': plan['old']['version']}
        archived = not plan['payload']['blocks'] and bool(plan['removed_blocks'])
        if archived:
            ctx.db.execute('UPDATE objects SET archived_at=? WHERE project_id=? AND id=?', (now(), ctx.project_id, plan['object_id']))
            ctx.changed_refs.append({'object_id':plan['object_id'],'field':'archived_at','deleted':True})
        output.append({**result, 'archived':archived, 'updated_blocks': plan['changed_blocks'], 'removed_blocks': plan['removed_blocks'],
                       'basis': plan['basis'], 'requires_recheck_blocks': plan['changed_blocks'] if plan['old'] else [],
                       'changed': plan['changed']})
    return {'effect': 'changed' if any(p['changed'] for p in plans) else 'noop', 'documents': output}


def _source_details(ctx, refs):
    result = []
    for ref in refs:
        row = ctx.db.execute('SELECT s.id,s.cached_title,s.canonical_url FROM source_versions v JOIN sources s ON s.project_id=v.project_id AND s.id=v.source_id WHERE v.project_id=? AND v.id=?', (ctx.project_id, ref['source_version_id'])).fetchone()
        result.append({**ref, **({'source_id': row['id'], 'title': row['cached_title'], 'canonical_url': row['canonical_url']} if row else {})})
    return result


def prepare_review(ctx, request):
    """Return current basis and stale paragraphs without creating a revision."""
    obj = _target(ctx, request['target'], allow_stale_scope=True)
    old = load_revision(ctx.db, ctx.project_id, obj['current_revision_id']) if obj and obj['current_revision_id'] else None
    selections = {}
    for selection in request.get('select_basis', []):
        selections.setdefault(selection['object_id'], set()).update(selection['item_ids'])
    affected = []
    if old:
        for bid, deps in old['dependencies'].items():
            stale = []
            for dep in deps:
                selections.setdefault(dep['object_id'], set()).add(dep['item_id'])
                if not _fresh(ctx, dep):
                    stale.append({k: dep[k] for k in ('object_id', 'revision_id', 'item_id')})
            if stale:
                affected.append({'block_id': bid, 'reason': 'dependency_changed', 'dependencies': stale})
    guide_objects = []
    if obj:
        guide_objects = [dict(row) for row in ctx.db.execute("SELECT * FROM objects WHERE project_id=? AND layer='draft' AND type_key='expression_guide' AND scope_key=? AND archived_at IS NULL", (ctx.project_id, 'review:' + obj['id']))]
        for guide in guide_objects:
            selections.setdefault(guide['id'], set()).add('*')
    if not selections:
        _error('DRAFT_CHANGE_REQUIRED', '初次生成需选择至少一个实际 draft 条目。')
    read_basis, selected, missing, guides = [], [], [], []
    selector_deps = []
    explicit = {s['object_id']: set(s['item_ids']) for s in request.get('select_basis', [])}
    for oid, item_ids in selections.items():
        draft = get_object(ctx.db, ctx.project_id, oid)
        if draft['layer'] != 'draft' or not draft['current_revision_id']:
            _error('INVALID_ITEM_REFERENCE', 'review 只能读取有效 draft 依据。', object_id=oid)
        revision = load_revision(ctx.db, ctx.project_id, draft['current_revision_id'])
        read_basis.append({'object_id': oid, 'revision_id': revision['id']})
        items = _items(revision)
        ids = list(items) if '*' in item_ids else sorted(item_ids)
        for item in ids:
            if item not in items:
                if item in explicit.get(oid, set()):
                    _error('INVALID_ITEM_REFERENCE', '选取的 draft 条目不存在。', object_id=oid, item_id=item)
                missing.append({'object_id': oid, 'item_id': item})
                continue
            entry = {**deepcopy(items[item]), 'object_id': oid, 'revision_id': revision['id'],
                     'fingerprint': fingerprint(ctx.db, ctx.project_id, revision['id'], item),
                     'source_refs': _source_details(ctx, revision.get('sources', {}).get(item, [])),
                     'dependencies': _deps(revision, item), 'fresh': is_fresh(ctx.db, ctx.project_id, revision['id'], item)}
            selected.append(entry)
            selector_deps.append({'object_id': oid, 'revision_id': revision['id'], 'item_id': item})
            if draft['type_key'] == 'expression_guide':
                guides.append(entry)
    if not old and not selected:
        _error('DRAFT_CHANGE_REQUIRED', '初次生成需选择至少一个实际 draft 条目。')
    available = []
    requested = set(request.get('cause_change_ids', []))
    basis_map = {entry['object_id']: entry['revision_id'] for entry in read_basis}
    if old:
        for change in _changes(ctx):
            eligible = []
            for bid, old_deps in old['dependencies'].items():
                next_deps = [d for d in selector_deps if any(d['object_id'] == prior['object_id'] and (prior['item_id'] == '*' or d['item_id'] == prior['item_id']) for prior in old_deps)]
                try:
                    _causes(ctx, [change['id']], oid=obj['id'], block=bid, old_deps=old_deps,
                            new_deps=next_deps, lineage=old['lineage'].get(bid, {}), read_basis=basis_map)
                    eligible.append(bid)
                except YuError as exc:
                    if exc.code not in {'DRAFT_CHANGE_REQUIRED', 'CAUSE_ALREADY_APPLIED'}:
                        raise
            structural = False
            try:
                _causes(ctx, [change['id']], oid=obj['id'], block='*', old_deps=[], new_deps=[],
                        lineage=old['lineage'].get(_STRUCTURE, {}), read_basis=basis_map, structural=True,
                        first_seq=_first_publication_seq(ctx, obj['id']) if _STRUCTURE not in old['lineage'] else None)
                structural = True
            except YuError as exc:
                if exc.code not in {'DRAFT_CHANGE_REQUIRED', 'CAUSE_ALREADY_APPLIED'}:
                    raise
            if eligible or structural:
                available.append({'change_id': change['id'], 'history_cursor': change['seq'], 'reason': change['reason'],
                                  'changed_refs': json.loads(change['changed_refs_json']), 'requested': change['id'] in requested,
                                  'eligible_blocks': eligible, 'structural': structural})
    checks = [] if not obj else [dict(row) for row in ctx.db.execute('SELECT c.* FROM review_checks c JOIN object_revisions r ON r.project_id=c.project_id AND r.id=c.review_revision_id WHERE r.project_id=? AND r.object_id=? ORDER BY c.created_at', (ctx.project_id, obj['id']))]
    return {'target': request['target'], 'object_id': obj['id'] if obj else None,
            'current_revision_id': old['id'] if old else None,
            'document': None if not old else {**old['payload'], 'dependencies': old['dependencies'], 'lineage': old['lineage']},
            'read_basis': read_basis, 'selected_items': selected, 'affected_blocks': affected,
            'missing_basis': missing, 'available_causes': available, 'expression_guides': guides, 'review_checks': checks}
