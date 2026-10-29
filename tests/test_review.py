"""Review behavior against real SQLite storage (no model or network doubles)."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from yuplus.core import Context, YuError, canonical, digest, insert, load_revision, now, write_revision
from yuplus.review import prepare_review, publish_review

SCHEMA = Path(__file__).resolve().parents[1] / 'docs/superpowers/specs/contracts/v0.1/schema.sql'


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript(SCHEMA.read_text())
        insert(self.db, 'projects', id='prj_one', name='展览', created_at=now(), updated_at=now())
        insert(self.db, 'projects', id='prj_other', name='另一个项目', created_at=now(), updated_at=now())
        self.db.commit()
        self.serial = 0
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '100000000', 'currency': 'CNY'}, 'other': {'note': '不变'}}, 'chg_budget1')

    def ctx(self, change=None):
        self.serial += 1
        return Context(self.db, Path(self.temp.name), 'prj_one', change or f'chg_test{self.serial}')

    def receipt(self, ctx, command, data):
        insert(self.db, 'changes', id=ctx.change_id, project_id=ctx.project_id, command=command,
               effect='changed', request_id=f'req_{ctx.change_id}', request_hash=digest(data),
               actor_json='{}', reason='测试', causal_change_ids_json=canonical(ctx.causal_change_ids),
               changed_refs_json=canonical(ctx.changed_refs), result_json=canonical(data), created_at=now())

    def draft(self, oid, typ, data, change, *, scope='project', deps=None):
        ctx = self.ctx(change)
        with self.db:
            if not self.db.execute('SELECT 1 FROM objects WHERE project_id=? AND id=?', ('prj_one', oid)).fetchone():
                insert(self.db, 'objects', project_id='prj_one', id=oid, layer='draft', type_key=typ,
                       scope_key=scope, created_at=now())
            old = self.db.execute('SELECT current_revision_id FROM objects WHERE project_id=? AND id=?', ('prj_one', oid)).fetchone()[0]
            old_items = {} if not old else {i['item_id']: i['data'] for i in load_revision(self.db, 'prj_one', old)['payload']['items']}
            changed = [key for key in set(data) | set(old_items) if data.get(key) != old_items.get(key)]
            if deps:
                changed = list(data)
            payload = {'title': typ, 'items': [{'item_id': key, 'data': value, 'epistemic_kind': 'hypothesis'} for key, value in data.items()], 'item_order': list(data)}
            result = write_revision(ctx, oid, payload, dependencies=deps or {}, changed_items=changed)
            self.receipt(ctx, 'draft.apply', result)
        return result

    def dep(self, item='budget', revision=None, oid='obj_budget', kind='fact'):
        revision = revision or self.budget['revision_id']
        return {'dependency_id': f'dep_{item}', 'object_id': oid, 'revision_id': revision, 'item_id': item, 'kind': kind}

    def doc(self, *, base=None, oid=None, text='预算 100 万', causes=None, deps=None, block='budget', basis=None, **extra):
        target = {'type_key': 'debrief', 'scope_key': 'project'}
        if oid:
            target['object_id'] = oid
        deps = deps or [self.dep()]
        document = {'target': target, 'base_revision': base, 'read_basis': basis or [{'object_id': d['object_id'], 'revision_id': d['revision_id']} for d in deps],
                    'structure_cause_change_ids': [], 'set_blocks': [{'block_id': block, 'markdown': text, 'dependencies': deps, 'cause_change_ids': causes or []}]}
        document.update(extra)
        return document

    def publish(self, *docs, change=None):
        ctx = self.ctx(change)
        with self.db:
            result = publish_review(ctx, {'api_version': '1', 'command': 'review.publish', 'reason': '整理成果', 'documents': list(docs)})
            self.receipt(ctx, 'review.publish', result)
        return result['documents'][0]

    def updated(self, initial, **kw):
        return self.doc(base=initial['revision_id'], oid=initial['object_id'], **kw)

    def assertCode(self, code, fn):
        with self.assertRaises(YuError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def test_initial_review_persists_document_and_prepare_is_read_only(self):
        before = self.db.total_changes
        data = prepare_review(self.ctx(), {'target': {'type_key': 'debrief', 'scope_key': 'project'}, 'cause_change_ids': [], 'select_basis': [{'object_id': 'obj_budget', 'item_ids': ['budget']}]})
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(data['selected_items'][0]['data']['min_minor'], '100000000')
        saved = self.publish(self.doc())
        self.assertEqual(saved['version'], 1)
        self.assertEqual(load_revision(self.db, 'prj_one', saved['revision_id'])['payload']['blocks'][0]['markdown'], '预算 100 万')

    def test_direct_rewrite_without_draft_change_is_rejected(self):
        saved = self.publish(self.doc())
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: self.publish(self.updated(saved, text='缩短措辞')))
        self.assertEqual(self.db.execute('SELECT current_revision_id FROM objects WHERE id=?', (saved['object_id'],)).fetchone()[0], saved['revision_id'])

    def test_initial_adopted_draft_cause_cannot_be_reused(self):
        saved = self.publish(self.doc())
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(self.updated(saved, text='另一种表达', causes=['chg_budget1'])))

    def test_draft_update_enables_exactly_one_rewrite_per_block(self):
        saved = self.publish(self.doc())
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}, 'other': {'note': '不变'}}, 'chg_budget2')
        new = self.publish(self.updated(saved, text='预算 60 万', causes=['chg_budget2']))
        self.assertEqual(new['version'], 2)
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(self.updated(new, text='再换个说法', causes=['chg_budget2'])))

    def test_unrelated_sibling_change_preserves_unmodified_block(self):
        saved = self.publish(self.doc())
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '100000000', 'currency': 'CNY'}, 'other': {'note': '更新兄弟条目'}}, 'chg_other')
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: self.publish(self.updated(saved, text='借无关原因重写', causes=['chg_other'])))
        prepared = prepare_review(self.ctx(), {'target': {'type_key': 'debrief', 'scope_key': 'project'}, 'cause_change_ids': [], 'select_basis': []})
        self.assertEqual(prepared['affected_blocks'], [])

    def test_stale_read_basis_is_rejected(self):
        saved = self.publish(self.doc())
        pending = self.updated(saved, text='旧依据', causes=['chg_budget1'])
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '50000000', 'currency': 'CNY'}}, 'chg_budget2')
        self.assertCode('DRAFT_BASIS_CHANGED', lambda: self.publish(pending))

    def test_source_change_is_never_a_review_cause(self):
        saved = self.publish(self.doc())
        ctx = self.ctx('chg_source')
        with self.db:
            self.receipt(ctx, 'source.import', {'snapshot_id': 'sv_none'})
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: self.publish(self.updated(saved, text='无 draft 更新', causes=['chg_source'])))

    def test_expression_guide_allows_rewrite_and_scopes_it(self):
        saved = self.publish(self.doc())
        guide = self.draft('obj_guide', 'expression_guide', {'concise': {'review_object_id': saved['object_id'], 'block_ids': ['budget'], 'instruction': '简短一点', 'intent': 'rewrite'}}, 'chg_guide', scope='review:' + saved['object_id'])
        dep = self.dep('concise', guide['revision_id'], 'obj_guide', 'expression')
        new = self.publish(self.updated(saved, text='预算：100 万', causes=['chg_guide'], deps=[self.dep(), dep]))
        self.assertEqual(new['version'], 2)
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(self.updated(new, text='预算是一百万', causes=['chg_guide'], deps=[self.dep(), dep])))

    def test_stale_retained_block_prevents_partial_publish(self):
        d = self.doc()
        d['set_blocks'].append({'block_id': 'delivery', 'markdown': '按预算交付', 'dependencies': [self.dep()], 'cause_change_ids': []})
        saved = self.publish(d)
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}}, 'chg_budget2')
        self.assertCode('STALE_DEPENDENCY', lambda: self.publish(self.updated(saved, text='预算 60 万', causes=['chg_budget2'])))

    def test_a_single_cause_can_update_multiple_dependent_blocks(self):
        d = self.doc()
        d['set_blocks'].append({'block_id': 'delivery', 'markdown': '按预算交付', 'dependencies': [self.dep()], 'cause_change_ids': []})
        saved = self.publish(d)
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}}, 'chg_budget2')
        update = self.updated(saved, text='预算 60 万', causes=['chg_budget2'])
        update['set_blocks'].append({'block_id': 'delivery', 'markdown': '按 60 万交付', 'dependencies': [self.dep()], 'cause_change_ids': ['chg_budget2']})
        new = self.publish(update)
        self.assertEqual(set(new['updated_blocks']), {'budget', 'delivery'})

    def test_removed_block_retains_consumed_cause(self):
        d = self.doc()
        d['set_blocks'].append({'block_id': 'keep', 'markdown': '保留段落', 'dependencies': [self.dep('other')], 'cause_change_ids': []})
        saved = self.publish(d)
        guide = self.draft('obj_guide', 'expression_guide', {'omit': {'review_object_id': saved['object_id'], 'block_ids': ['budget'], 'instruction': '删除预算段', 'intent': 'omit'}}, 'chg_omit', scope='review:' + saved['object_id'])
        update = self.updated(saved, deps=[self.dep('omit', guide['revision_id'], 'obj_guide', 'expression')])
        del update['set_blocks']
        update['remove_blocks'] = [{'block_id': 'budget', 'cause_change_ids': ['chg_omit']}]
        removed = self.publish(update)
        self.assertEqual(removed['removed_blocks'], ['budget'])
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(self.updated(removed, text='恢复预算', causes=['chg_omit'], deps=[self.dep(), self.dep('omit', guide['revision_id'], 'obj_guide', 'expression')])))

    def test_new_block_id_cannot_reuse_initial_draft_change(self):
        saved = self.publish(self.doc())
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(self.updated(saved, text='预算换一个段落 ID', block='new_budget', causes=['chg_budget1'])))

    def test_title_change_requires_fresh_expression_guide(self):
        saved = self.publish(self.doc())
        update = self.updated(saved, title='随意改标题')
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: self.publish(update))

    def test_bad_second_document_rolls_back_first(self):
        first = self.doc()
        second = self.doc()
        second['target'] = {'type_key': 'advancement', 'scope_key': 'project'}
        second['set_blocks'][0]['dependencies'][0]['revision_id'] = 'rev_missing'
        self.assertCode('DRAFT_BASIS_CHANGED', lambda: self.publish(first, second))
        self.assertEqual(self.db.execute("SELECT count(*) FROM objects WHERE layer='review'").fetchone()[0], 0)

    def test_initial_prepare_requires_some_real_basis(self):
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: prepare_review(self.ctx(), {'target': {'type_key': 'debrief', 'scope_key': 'project'}, 'cause_change_ids': [], 'select_basis': []}))

    def test_arbitrary_new_scope_cannot_bypass_existing_review(self):
        d = self.doc()
        d['target']['scope_key'] = 'anything'
        self.assertCode('INVALID_SCOPE', lambda: self.publish(d))

    def test_prepare_does_not_offer_already_consumed_causes(self):
        saved = self.publish(self.doc())
        args = {'target': {'type_key': 'debrief', 'scope_key': 'project'}, 'cause_change_ids': ['chg_budget1'], 'select_basis': []}
        data = prepare_review(self.ctx(), args)
        self.assertEqual(data['available_causes'], [])
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}}, 'chg_budget2')
        data = prepare_review(self.ctx(), args)
        self.assertEqual([c['change_id'] for c in data['available_causes']], ['chg_budget2'])

    def test_sibling_only_version_rebinding_does_not_create_review_version(self):
        saved = self.publish(self.doc())
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '100000000', 'currency': 'CNY'}, 'other': {'note': '无关更新'}}, 'chg_other')
        result = self.publish(self.updated(saved))
        self.assertEqual(result['revision_id'], saved['revision_id'])
        self.assertFalse(result['changed'])

    def test_independent_block_may_consume_cause_before_latest_document_revision(self):
        initial = self.doc()
        initial['set_blocks'].append({'block_id': 'other', 'markdown': '其他说明', 'dependencies': [self.dep('other')], 'cause_change_ids': []})
        saved = self.publish(initial)
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '100000000', 'currency': 'CNY'}, 'other': {'note': '不变'}}, 'chg_no_semantic')
        guide = self.draft('obj_guide', 'expression_guide', {
            'budget_words': {'review_object_id': saved['object_id'], 'block_ids': ['budget'], 'instruction': '精简预算', 'intent': 'rewrite'},
            'other_words': {'review_object_id': saved['object_id'], 'block_ids': ['other'], 'instruction': '精简说明', 'intent': 'rewrite'},
        }, 'chg_two_guides', scope='review:' + saved['object_id'])
        first = self.publish(self.updated(saved, text='预算 100 万元', causes=['chg_two_guides'], deps=[self.dep(), self.dep('budget_words', guide['revision_id'], 'obj_guide', 'expression')]))
        second = self.publish(self.updated(first, block='other', text='其他', causes=['chg_two_guides'], deps=[self.dep('other'), self.dep('other_words', guide['revision_id'], 'obj_guide', 'expression')]))
        self.assertEqual(second['version'], 3)

    def test_expression_guide_cannot_rewrite_another_block(self):
        initial = self.doc()
        initial['set_blocks'].append({'block_id': 'other', 'markdown': '其他', 'dependencies': [self.dep('other')], 'cause_change_ids': []})
        saved = self.publish(initial)
        guide = self.draft('obj_guide', 'expression_guide', {'concise': {'review_object_id': saved['object_id'], 'block_ids': ['other'], 'instruction': '仅改其他段落', 'intent': 'rewrite'}}, 'chg_wrong_guide', scope='review:' + saved['object_id'])
        dep = self.dep('concise', guide['revision_id'], 'obj_guide', 'expression')
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: self.publish(self.updated(saved, text='不该改预算', causes=['chg_wrong_guide'], deps=[self.dep(), dep])))

    def test_fresh_structure_guide_can_change_title_only_once(self):
        saved = self.publish(self.doc())
        guide = self.draft('obj_guide', 'expression_guide', {'title': {'review_object_id': saved['object_id'], 'block_ids': ['*'], 'instruction': '标题换成预算简报', 'intent': 'structure'}}, 'chg_title', scope='review:' + saved['object_id'])
        doc = self.updated(saved, title='预算简报', basis=[{'object_id': 'obj_budget', 'revision_id': self.budget['revision_id']}, {'object_id': 'obj_guide', 'revision_id': guide['revision_id']}], structure_cause_change_ids=['chg_title'])
        changed = self.publish(doc)
        self.assertEqual(changed['version'], 2)
        doc['base_revision'] = changed['revision_id']
        doc['title'] = '再次改标题'
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(doc))

    def test_transitively_stale_draft_cannot_be_used_in_initial_review(self):
        from yuplus.core import resolve_dependency
        deps = {'estimate': [resolve_dependency(self.ctx(), self.dep())]}
        derived = self.draft('obj_allocation', 'budget_allocation', {'estimate': {'area': '制作'}}, 'chg_allocation', deps=deps)
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}}, 'chg_budget2')
        self.assertCode('STALE_DEPENDENCY', lambda: self.publish(self.doc(deps=[self.dep('estimate', derived['revision_id'], 'obj_allocation', 'derivation')])))

    def test_lineage_records_authored_revision_and_preserves_retained_paragraph(self):
        initial = self.doc()
        initial['set_blocks'].append({'block_id': 'other', 'markdown': '其他说明', 'dependencies': [self.dep('other')], 'cause_change_ids': []})
        saved = self.publish(initial)
        history = load_revision(self.db, 'prj_one', saved['revision_id'])['lineage']
        self.assertEqual(history['budget']['last_authored_revision_id'], saved['revision_id'])
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}, 'other': {'note': '不变'}}, 'chg_budget2')
        updated = self.publish(self.updated(saved, text='预算 60 万', causes=['chg_budget2']))
        history = load_revision(self.db, 'prj_one', updated['revision_id'])['lineage']
        self.assertEqual(history['budget']['last_authored_revision_id'], updated['revision_id'])
        self.assertEqual(history['other']['last_authored_revision_id'], saved['revision_id'])

    def test_draft_title_only_change_cannot_authorize_fact_paragraph_rewrite(self):
        saved = self.publish(self.doc())
        current = load_revision(self.db, 'prj_one', self.budget['revision_id'])
        payload = current['payload']
        payload['title'] = '换个标题'
        ctx = self.ctx('chg_draft_title')
        with self.db:
            self.budget = write_revision(ctx, 'obj_budget', payload, changed_items=['*'])
            self.receipt(ctx, 'draft.apply', self.budget)
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: self.publish(self.updated(saved, text='重写预算段', causes=['chg_draft_title'])))

    def test_transitive_reversion_before_publication_is_already_consumed(self):
        from yuplus.core import resolve_dependency
        deps = {'estimate': [resolve_dependency(self.ctx(), self.dep())]}
        derived = self.draft('obj_allocation', 'budget_allocation', {'estimate': {'area': '制作'}}, 'chg_allocation', deps=deps)
        self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}}, 'chg_budget2')
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '100000000', 'currency': 'CNY'}, 'other': {'note': '不变'}}, 'chg_budget_reverted')
        dep = self.dep('estimate', derived['revision_id'], 'obj_allocation', 'derivation')
        saved = self.publish(self.doc(deps=[dep]))
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(self.updated(saved, text='无新增 draft 就改写', causes=['chg_budget_reverted'], deps=[dep])))
        lineage = load_revision(self.db, 'prj_one', saved['revision_id'])['lineage']['budget']
        self.assertIn('chg_budget_reverted', lineage['applied_cause_ids'])

    def test_empty_wildcard_draft_cannot_support_initial_review(self):
        empty = self.draft('obj_empty', 'client_brief', {}, 'chg_empty')
        dep = {'dependency_id': 'dep_all', 'object_id': 'obj_empty', 'revision_id': empty['revision_id'], 'item_id': '*', 'kind': 'fact'}
        self.assertCode('DRAFT_CHANGE_REQUIRED', lambda: self.publish(self.doc(deps=[dep])))

    def test_transitive_reversion_after_publication_can_be_consumed_once(self):
        from yuplus.core import resolve_dependency
        deps = {'estimate': [resolve_dependency(self.ctx(), self.dep())]}
        derived = self.draft('obj_allocation', 'budget_allocation', {'estimate': {'area': '制作'}}, 'chg_allocation', deps=deps)
        dep = self.dep('estimate', derived['revision_id'], 'obj_allocation', 'derivation')
        saved = self.publish(self.doc(deps=[dep]))
        self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '60000000', 'currency': 'CNY'}}, 'chg_budget2')
        self.budget = self.draft('obj_budget', 'budget_range', {'budget': {'min_minor': '100000000', 'currency': 'CNY'}, 'other': {'note': '不变'}}, 'chg_budget_reverted')
        updated = self.publish(self.updated(saved, text='预算回到 100 万', causes=['chg_budget_reverted'], deps=[dep]))
        self.assertEqual(updated['version'], 2)
        self.assertCode('CAUSE_ALREADY_APPLIED', lambda: self.publish(self.updated(updated, text='再次改写', causes=['chg_budget_reverted'], deps=[dep])))

    def test_deleted_round_scope_can_be_cleaned_up_but_not_rewritten(self):
        self.draft('obj_resources','resources',{'alice':{'name':'Alice'}},'chg_resources')
        self.draft('obj_deliverables','deliverables',{'deliver':{'deliverable':'视频','round_key':'first'}},'chg_delivery')
        doc=self.doc();doc['target']={'type_key':'advancement','scope_key':'round:first'}
        saved=self.publish(doc)
        self.draft('obj_deliverables','deliverables',{},'chg_remove_delivery')
        self.budget=self.draft('obj_budget','budget_range',{'budget':{'min_minor':'60000000','currency':'CNY'}},'chg_budget2')
        update=self.updated(saved,causes=['chg_budget2']);update['target']={**doc['target'],'object_id':saved['object_id']}
        self.assertCode('INVALID_SCOPE',lambda:self.publish(update))
        prepared=prepare_review(self.ctx(),{'target':update['target'],'cause_change_ids':[],'select_basis':[]})
        update.pop('set_blocks');update['remove_blocks']=[{'block_id':'budget','cause_change_ids':['chg_budget2']}];update['read_basis']=prepared['read_basis']
        self.assertTrue(self.publish(update)['archived'])


if __name__ == '__main__':
    unittest.main()
