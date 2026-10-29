"""Soft deletion through existing versioned mutations; never erase evidence or files."""
from .core import YuError, affected_objects, get_object, load_revision, now, write_revision
from .source import _get_source


def change_lifecycle(ctx, command, request):
    layer, action = command.split('.')
    if not request['reason'].strip():
        raise YuError('INVALID_INPUT', '删除或恢复必须说明原因。')
    source = layer == 'source'
    record = (_get_source if source else get_object)(ctx.db, ctx.project_id, request['source_id' if source else 'object_id'])
    if not source and record['layer'] != layer:
        raise YuError('INVALID_SCOPE', '对象层与命令不一致。')
    if not source and action == 'restore':
        from .app import CONTRACTS
        import json
        catalog = json.loads((CONTRACTS/'object-types.json').read_text())
        supported = {t['type_key'] for t in catalog['objects'] + catalog['internal_types']}
        from .review import _REVIEW_TYPES
        if record['type_key'] not in supported | _REVIEW_TYPES:
            raise YuError('INVALID_SCOPE', '该类型不属于当前可用对象。')
        if record['type_key'] == 'expression_guide':
            target = ctx.db.execute('SELECT type_key FROM objects WHERE project_id=? AND id=?', (ctx.project_id, record['scope_key'].removeprefix('review:'))).fetchone()
            if not target or target[0] not in _REVIEW_TYPES:
                raise YuError('INVALID_SCOPE', '编写依据的目标不是当前可用成果。')
    head = record['latest_snapshot_id' if source else 'current_revision_id']
    if request['base_snapshot_id' if source else 'base_revision'] != head:
        raise YuError('BASE_REVISION_CONFLICT', '版本已变化，请重新读取后再删除或恢复。')
    deleted = action == 'delete'
    identity = {'source_id' if source else 'object_id': record['id']}
    result = {**identity, 'snapshot_id' if source else 'revision_id': head,
              'effect': 'noop', 'archived': bool(record['archived_at']), 'retained_data': True,
              'deletion_mode': 'soft'}
    if bool(record['archived_at']) == deleted:
        return result
    if source:
        # Citations retain the original snapshot and remain readable after hiding the source.
        references = [dict(r) for r in ctx.db.execute('''SELECT DISTINCT o.id AS object_id,rs.item_id
            FROM revision_sources rs JOIN source_versions v ON v.project_id=rs.project_id AND v.id=rs.source_version_id
            JOIN objects o ON o.project_id=rs.project_id AND o.current_revision_id=rs.revision_id
            WHERE v.project_id=? AND v.source_id=? AND o.archived_at IS NULL''', (ctx.project_id, record['id']))]
        result['referenced_by'] = references
        ctx.db.execute('UPDATE sources SET observation_generation=observation_generation+1 WHERE project_id=? AND id=?', (ctx.project_id, record['id']))
    else:
        old = load_revision(ctx.db, ctx.project_id, head)
        if deleted and layer == 'draft' and old['payload']['items']:
            from .draft import apply_draft
            body = {'api_version':'1', 'command':'draft.apply', 'reason':request['reason'],
                    'objects':[{'op_id':'delete', 'object_id':record['id'], 'type_key':record['type_key'],
                                'scope_key':record['scope_key'], 'base_revision':head,
                                'remove_items':[i['item_id'] for i in old['payload']['items']]}],
                    'decisions':request.get('decisions', [])}
            if request.get('instruction_source_version_id'):
                body['instruction_source_version_id'] = request['instruction_source_version_id']
            changes = apply_draft(ctx, body)
            result.update(changes['objects'][0])
            result['decisions'] = changes['decisions']
        elif deleted and layer == 'review' and old['payload']['blocks']:
            from .review import publish_review
            changes = publish_review(ctx, {'api_version':'1','command':'review.publish','reason':request['reason'],
                'documents':[{'target':{'object_id':record['id'],'type_key':record['type_key'],'scope_key':record['scope_key']},
                              'base_revision':head,'read_basis':request['read_basis'],'structure_cause_change_ids':[],
                              'remove_blocks':[{'block_id':b['block_id'],'cause_change_ids':request['cause_change_ids']}
                                               for b in old['payload']['blocks']]}]})
            result.update(changes['documents'][0])
        else:
            # Empty objects can be hidden/reopened without inventing content. Preserve consumed causes.
            result.update(write_revision(ctx, record['id'], old['payload'], sources=old['sources'],
                                         dependencies=old['dependencies'], lineage=old['lineage']))
    table = 'sources' if source else 'objects'
    ctx.db.execute(f'UPDATE {table} SET archived_at=? WHERE project_id=? AND id=?',
                   (now() if deleted else None, ctx.project_id, record['id']))
    ctx.changed_refs.append({**identity, 'field':'archived_at', 'deleted':deleted})
    if not source:
        impacts = affected_objects(ctx.db, ctx.project_id)
        result.update(affected_draft_items=impacts['draft'], affected_reviews=impacts['review'])
    return {**result, 'effect':'changed', 'archived':deleted}
