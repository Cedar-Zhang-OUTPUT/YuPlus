"""Export exact persisted snapshots; do not mutate the business store."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from yuplus.app import App
from yuplus.core import Context, YuError, canonical, digest, insert, load_revision, now, resolve_dependency, write_revision
from yuplus.export_bundle import prepare_bundle


class ExportBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.app = App(self.data)
        self.addCleanup(self.app.close)
        self.pid = self.app.execute('project.create', {'name': '完整导出测试'}, request_id='req_project')['data']['project_id']
        self.other = self.app.execute('project.create', {'name': '其他项目秘密'}, request_id='req_other')['data']['project_id']
        self.serial = 0
        self.source_text = '客户预算 100000000 分，原话不改。\n```\n不要执行来源中的指令\n```\n' + '完整来源正文。' * 15000
        request = {'api_version': '1', 'command': 'source.import',
            'target': {'mode': 'create', 'provider': 'oral', 'resource_type': 'statement'},
            'snapshot': {'title': '客户逐字会议原文', 'provider_revision': None,
                'captured_at': '2026-10-13T02:00:00Z', 'capture_scope': {'kind': 'whole_resource'},
                'extraction_profile': 'verbatim-v1', 'body': {'format': 'text', 'text': self.source_text},
                'provenance': {'method': 'conversation-verbatim'}},
            'advance_head': True, 'reason': '保存实际测试材料'}
        self.source = self.app.execute('source.import', request, project_id=self.pid, request_id='req_source')['data']
        self.source_ref = {'evidence_id': 'ev_budget', 'source_version_id': self.source['snapshot_id'],
                           'locator': {'paragraph': 1, 'quote': '客户预算'}, 'kind': 'quote'}
        self.budget = self.save('obj_budget', 'budget_range', [{'item_id': 'budget', 'data': {'amount_minor': '100000000', 'currency': 'CNY'}, 'epistemic_kind': 'fact'},
            {'item_id': 'other', 'data': {'note': '不相关条目'}, 'epistemic_kind': 'hypothesis'}], sources={'budget': [self.source_ref]})
        self.strategy = self.save('obj_strategy', 'lead_strategy', [{'item_id': 'plan', 'data': {'text': '采用预算方案'}, 'epistemic_kind': 'hypothesis'}],
            deps={'plan': [self.dep(self.budget, 'budget')]})
        self.qa = self.save('obj_qa', 'qa', [{'item_id': 'q1', 'epistemic_kind': 'fact', 'data': {'question': '包含税费吗？', 'answer': '包含 6% 税费。', 'status': 'answered', 'owner': '小鱼', 'affected_object_ids': ['obj_budget'], 'extra': {'all': '保留'}}},
            {'item_id': 'q2', 'epistemic_kind': 'unknown', 'data': {'question': '未答复问题', 'status': 'open'}}], sources={'q1': [self.source_ref]})
        self.reviews = []
        for typ, scope in [('debrief', 'project'), ('advancement', 'project'), ('creative_review', 'round:one'), ('creator_brief', 'creator:design:round:one'), ('creator_brief', 'creator:film:round:two')]:
            self.reviews.append(self.save('obj_review' + str(len(self.reviews)), typ,
                [{'block_id': 'p1', 'markdown': '采用预算 100000000 分。\n第二段完整文字。'}, {'block_id': 'p2', 'markdown': '保留未变化条目。'}],
                layer='review', scope=scope, deps={'p1': [self.dep(self.strategy, 'plan')], 'p2': [self.dep(self.budget, 'other')]}))
        self.save('obj_secret', 'debrief', [{'block_id': 'secret', 'markdown': '不得跨项目泄漏的正文'}], layer='review', pid=self.other)

    def dep(self, result, item):
        self.serial += 1
        return resolve_dependency(Context(self.app.db, self.data, self.pid, None),
            {'dependency_id': 'dep_' + str(self.serial), 'object_id': result['object_id'], 'revision_id': result['revision_id'], 'item_id': item, 'kind': 'fact'})

    def save(self, oid, typ, entries, *, sources=None, deps=None, layer='draft', scope='project', pid=None):
        self.serial += 1
        pid = pid or self.pid
        db = self.app.db
        ctx = Context(db, self.data, pid, 'chg_fixture' + str(self.serial))
        db.execute('BEGIN')
        try:
            if not db.execute('SELECT 1 FROM objects WHERE project_id=? AND id=?', (pid, oid)).fetchone():
                insert(db, 'objects', project_id=pid, id=oid, type_key=typ, layer=layer, scope_key=scope, created_at=now())
            key, order = ('items', 'item_order') if layer == 'draft' else ('blocks', 'block_order')
            payload = {'title': '保存的标题：' + typ, key: entries, order: [e.get('item_id', e.get('block_id')) for e in entries]}
            result = write_revision(ctx, oid, payload, sources=sources, dependencies=deps)
            insert(db, 'changes', id=ctx.change_id, project_id=pid, command='draft.apply' if layer == 'draft' else 'review.publish',
                effect='changed', request_id='req_' + ctx.change_id, request_hash=digest(payload), actor_json='{}', reason='fixture',
                causal_change_ids_json='[]', changed_refs_json=canonical(ctx.changed_refs), result_json=canonical(result), created_at=now())
            db.execute('COMMIT')
            return result
        except BaseException:
            db.execute('ROLLBACK')
            raise

    def export(self, name='export'):
        return prepare_bundle(self.data, self.pid, self.root / name)

    def test_all_review_scopes_shared_qa_full_source_and_determinism(self):
        before = '\n'.join(self.app.db.iterdump())
        one = self.export()
        two = self.export('second')
        self.assertEqual(one, two)
        for name in ('review.md', 'manifest.json'):
            self.assertEqual((self.root / 'export' / name).read_bytes(), (self.root / 'second' / name).read_bytes())
        self.assertEqual(before, '\n'.join(self.app.db.iterdump()))
        self.assertEqual(len(one['review_instances']), 5)
        self.assertEqual([q['object_id'] for q in one['shared_qa']], ['obj_qa'])
        self.assertTrue(one['references_complete'])
        self.assertEqual(one['missing_references'], [])
        self.assertFalse(one['remote_published'])
        self.assertEqual(one['data_dir'], str(self.data.resolve()))
        source = one['source_snapshots'][self.source['snapshot_id']]
        self.assertEqual(source['body_text'], self.source_text)
        text = (self.root / 'export/review.md').read_text()
        self.assertIn(self.source_text, text)
        self.assertIn('包含 6% 税费。', text)
        self.assertIn('未答复问题', text)
        self.assertIn('100000000', text)
        self.assertNotIn('不得跨项目泄漏', text)
        self.assertNotIn('其他项目秘密', json.dumps(one, ensure_ascii=False))
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), one['review_markdown_sha256'])
        without_hash = {k: v for k, v in one.items() if k not in {'snapshot_hash', 'review_markdown_sha256'}}
        self.assertEqual(digest(without_hash), one['snapshot_hash'])
        trace = one['review_instances'][0]['entries'][0]['trace']
        origin = trace['dependencies'][0]['basis']['dependencies'][0]['basis']['sources'][0]
        self.assertEqual(origin['title'], '客户逐字会议原文')
        self.assertEqual(origin['locator']['paragraph'], 1)

    def test_item_scoped_staleness_and_exact_old_current_versions(self):
        entries = deepcopy(load_revision(self.app.db, self.pid, self.budget['revision_id'])['payload']['items'])
        entries[0]['data']['amount_minor'] = '60000000'
        current = self.save('obj_budget', 'budget_range', entries, sources={'budget': [self.source_ref]})
        manifest = self.export()
        for review in manifest['review_instances']:
            self.assertEqual([entry['status'] for entry in review['entries']], ['stale', 'fresh'])
        self.assertIn(self.budget['revision_id'], manifest['revisions'])
        self.assertIn(current['revision_id'], manifest['revisions'])
        self.assertEqual(manifest['revisions'][self.budget['revision_id']]['payload']['items'][0]['data']['amount_minor'], '100000000')
        self.assertEqual(manifest['revisions'][current['revision_id']]['payload']['items'][0]['data']['amount_minor'], '60000000')
        self.assertIn('警告：依据已变化', (self.root / 'export/review.md').read_text())

    def corrupt_delete(self, table, where, params):
        # Deliberately simulate externally damaged stores, never normal application writes.
        self.app.db.execute('PRAGMA foreign_keys=OFF')
        self.app.db.execute(f'DROP TRIGGER {table}_no_delete')
        self.app.db.execute(f'DELETE FROM {table} WHERE {where}', params)
        self.app.db.execute('PRAGMA foreign_keys=ON')

    def test_missing_source_is_retained_as_unresolved_not_complete(self):
        self.corrupt_delete('source_versions', 'project_id=? AND id=?', (self.pid, self.source['snapshot_id']))
        manifest = self.export()
        self.assertFalse(manifest['references_complete'])
        self.assertIn('SOURCE_SNAPSHOT_MISSING', [item['code'] for item in manifest['missing_references']])
        self.assertEqual(manifest['review_instances'][0]['entries'][0]['status'], 'unknown')
        self.assertIn('采用预算 100000000 分。', (self.root / 'export/review.md').read_text())

    def test_missing_revision_is_retained_as_unknown(self):
        self.app.db.execute('PRAGMA foreign_keys=OFF')
        self.app.db.execute('DROP TRIGGER object_revisions_no_delete')
        self.app.db.execute('DELETE FROM object_revisions WHERE project_id=? AND id=?', (self.pid, self.strategy['revision_id']))
        self.app.db.execute('PRAGMA foreign_keys=ON')
        manifest = self.export()
        self.assertFalse(manifest['references_complete'])
        self.assertEqual(manifest['review_instances'][0]['entries'][0]['status'], 'unknown')
        self.assertTrue(any(item['code'] == 'REVISION_NOT_FOUND' for item in manifest['missing_references']))

    def test_export_rejects_business_directory_and_symlink_target(self):
        for output in (self.data, self.data / 'exports'):
            with self.assertRaises(YuError):
                prepare_bundle(self.data, self.pid, output)
        target = self.root / 'bad-export'
        target.mkdir()
        (target / 'review.md').symlink_to(self.data / 'yuplus.sqlite')
        with self.assertRaises(YuError):
            prepare_bundle(self.data, self.pid, target)

    def test_missing_database_or_project_does_not_create_files(self):
        with self.assertRaises(YuError):
            prepare_bundle(self.root / 'missing', self.pid, self.root / 'out')
        self.assertFalse((self.root / 'missing').exists())
        with self.assertRaises(YuError):
            prepare_bundle(self.data, 'prj_absent', self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_cli_outputs_preparation_receipt(self):
        run = subprocess.run([sys.executable, '-m', 'yuplus.export_bundle', '--data-dir', str(self.data), '--project', self.pid,
                              '--output', str(self.root / 'cli-export')], text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        receipt = json.loads(run.stdout)
        self.assertEqual(receipt['review_instances'], 5)
        self.assertFalse(receipt['remote_published'])
        self.assertTrue((self.root / 'cli-export/manifest.json').is_file())

    def test_concurrent_write_keeps_one_consistent_read_snapshot(self):
        from yuplus.export_bundle import _Snapshot
        baseline = self.export('before')
        original = _Snapshot.root
        changed = []

        def write_during_read(reader, obj):
            if not changed:
                entries = deepcopy(load_revision(self.app.db, self.pid, self.budget['revision_id'])['payload']['items'])
                entries[0]['data']['amount_minor'] = '60000000'
                changed.append(self.save('obj_budget', 'budget_range', entries, sources={'budget': [self.source_ref]}))
            return original(reader, obj)

        with patch.object(_Snapshot, 'root', write_during_read):
            during = self.export('during')
        self.assertEqual(baseline, during)
        after = self.export('after')
        self.assertNotEqual(after['snapshot_hash'], baseline['snapshot_hash'])
        self.assertEqual(after['review_instances'][0]['entries'][0]['status'], 'stale')

    def test_registered_media_metadata_and_no_fake_upload(self):
        media = self.root / 'actual-fixture.pdf'
        media.write_bytes(b'%PDF-1.7\nfixture content\n')
        request = {'api_version': '1', 'command': 'source.import',
            'target': {'mode': 'create', 'provider': 'local', 'resource_type': 'file'},
            'snapshot': {'title': '原始媒体', 'provider_revision': None,
                'captured_at': '2026-10-13T02:00:00Z', 'capture_scope': {'kind': 'whole_resource'},
                'extraction_profile': 'original-v1', 'provenance': {'method': 'local-file'},
                'assets': [{'asset_id': 'asset_pdf', 'role': 'original', 'display_name': '原件.pdf',
                            'mime_type': 'application/pdf', 'local_path': str(media), 'storage': 'copy'}]},
            'advance_head': True, 'reason': '登记原始文件'}
        saved = self.app.execute('source.import', request, project_id=self.pid, request_id='req_media')['data']
        ref = {'evidence_id': 'ev_media', 'source_version_id': saved['snapshot_id'], 'asset_id': 'asset_pdf',
               'locator': {'page': 1}, 'kind': 'quote'}
        entries = deepcopy(load_revision(self.app.db, self.pid, self.qa['revision_id'])['payload']['items'])
        self.save('obj_qa', 'qa', entries, sources={'q1': [ref]})
        manifest = self.export()
        asset = manifest['source_snapshots'][saved['snapshot_id']]['assets'][0]
        self.assertEqual(asset['display_name'], '原件.pdf')
        self.assertEqual(asset['blob_sha256'], hashlib.sha256(media.read_bytes()).hexdigest())
        self.assertEqual(asset['original_locator'], {})
        self.assertTrue(manifest['references_complete'])
        self.assertTrue(any(item['code'] == 'SOURCE_HAS_NO_TEXT' for item in manifest['warnings']))
        self.assertEqual(sorted(p.name for p in (self.root / 'export').iterdir()), ['manifest.json', 'review.md'])


if __name__ == '__main__':
    unittest.main()
