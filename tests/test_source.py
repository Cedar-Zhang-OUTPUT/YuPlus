"""Source import tests: provenance, immutable bytes, version reuse and replay."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest


class SourceTests(unittest.TestCase):
    def setUp(self):
        from yuplus.app import App
        from yuplus.core import YuError
        self.YuError = YuError
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = App(self.root / 'yu-data')
        self.addCleanup(self.app.close)
        self.pid = self.app.execute('project.create', {'name': '城市展'}, request_id='req_project')['data']['project_id']
        self.seq = 0

    def oral(self, text='客户提出预算为人民币 100 万元。'):
        return {'api_version': '1', 'command': 'source.import',
                'target': {'mode': 'create', 'provider': 'oral', 'resource_type': 'statement'},
                'snapshot': {'title': '首次会谈', 'provider_revision': None,
                    'captured_at': '2026-10-13T02:00:00Z',
                    'capture_scope': {'kind': 'whole_resource'},
                    'extraction_profile': 'verbatim-v1', 'body': {'format': 'text', 'text': text},
                    'provenance': {'method': 'conversation-verbatim', 'reported_by': '主策'}},
                'advance_head': True, 'reason': '保存用户原话'}

    def feishu(self):
        request = self.oral()
        request['target'] = {'mode': 'create', 'provider': 'feishu', 'resource_type': 'docx',
                             'provider_key': 'tenant_demo:docx_demo',
                             'canonical_url': 'https://example.feishu.cn/docx/docx_demo?from=copy#section'}
        request['snapshot']['provider_revision'] = '17'
        request['snapshot']['provenance'] = {'method': 'feishu-cli-docx'}
        return request

    def local(self, *, storage='copy', explicit_key=None):
        path = self.root / 'materials.pdf'
        path.write_bytes(b'%PDF-1.7\nimmutable original\n')
        request = self.oral('场地在一层。')
        request['target'] = {'mode': 'create', 'provider': 'local', 'resource_type': 'file'}
        if explicit_key:
            request['target']['provider_key'] = explicit_key
        request['snapshot']['assets'] = [{'asset_id': 'asset_original', 'role': 'original',
            'display_name': '场地资料.pdf', 'mime_type': 'application/pdf',
            'local_path': str(path), 'storage': storage}]
        return request, path

    def run_import(self, request, request_id=None, project_id=None):
        self.seq += 1
        return self.app.execute('source.import', request, project_id=project_id or self.pid,
                                request_id=request_id or f'req_source_{self.seq}')

    def append(self, request, previous):
        updated = deepcopy(request)
        updated['target'] = {'mode': 'append', 'source_id': previous['source_id'],
                             'base_snapshot_id': previous['head_snapshot_id']}
        return updated

    def test_oral_text_and_attribution_are_stored_exactly(self):
        text = '客户说：先按 60 万推进。\n这是原话。'
        result = self.run_import(self.oral(text))['data']
        from yuplus.source import show_source
        shown = show_source(self.app.db, self.pid, result['source_id'])
        self.assertEqual(shown['snapshot']['body'], {'format': 'text', 'text': text})
        self.assertEqual(shown['snapshot']['provenance']['reported_by'], '主策')
        self.assertEqual(result['snapshot_version'], 1)
        self.assertEqual(result['head_snapshot_id'], result['snapshot_id'])

    def test_feishu_identity_and_title_are_separate_from_sharing_parameters(self):
        request = self.feishu()
        result = self.run_import(request)['data']
        self.assertEqual(result['canonical_url'], 'https://example.feishu.cn/docx/docx_demo')
        request['target']['canonical_url'] = 'https://example.feishu.cn/docx/docx_demo?from=another'
        request['snapshot']['title'] = '同一材料的新标题'
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request)
        self.assertEqual(caught.exception.code, 'SOURCE_EXISTS')

    def test_append_unchanged_capture_reuses_snapshot_despite_new_capture_time(self):
        original = self.feishu()
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['captured_at'] = '2026-10-14T02:00:00Z'
        second = self.run_import(request)['data']
        self.assertEqual(second['effect'], 'noop')
        self.assertEqual(second['snapshot_id'], first['snapshot_id'])
        self.assertTrue(second['snapshot_reused'])

    def test_title_cache_update_does_not_rewrite_historical_title(self):
        original = self.feishu()
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['title'] = '已改名'
        second = self.run_import(request)['data']
        self.assertEqual(second['effect'], 'changed')
        self.assertEqual(second['snapshot_id'], first['snapshot_id'])
        from yuplus.source import show_source
        self.assertEqual(show_source(self.app.db, self.pid, first['source_id'])['snapshot']['title'], '首次会谈')

    def test_new_remote_revision_preserves_even_identical_text(self):
        original = self.feishu()
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['provider_revision'] = '18'
        second = self.run_import(request)['data']
        self.assertEqual(second['snapshot_version'], 2)
        self.assertNotEqual(second['snapshot_id'], first['snapshot_id'])

    def test_same_revision_different_text_is_rejected_without_new_snapshot(self):
        original = self.feishu()
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['body']['text'] = '偷偷变了'
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request)
        self.assertEqual(caught.exception.code, 'SOURCE_REVISION_CONFLICT')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM source_versions').fetchone()[0], 1)

    def test_unknown_revision_return_to_old_content_creates_new_version(self):
        original = self.oral('一百万')
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['body']['text'] = '六十万'
        second = self.run_import(request)['data']
        third = self.run_import(self.append(original, second))['data']
        self.assertEqual(third['snapshot_version'], 3)
        self.assertNotEqual(third['snapshot_id'], first['snapshot_id'])

    def test_old_known_revision_cannot_replace_newer_head(self):
        original = self.feishu()
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['provider_revision'] = '18'
        second = self.run_import(request)['data']
        old = self.append(original, second)
        with self.assertRaises(self.YuError) as caught:
            self.run_import(old)
        self.assertEqual(caught.exception.code, 'SOURCE_REVISION_OUTDATED')
        old['advance_head'] = False
        reused = self.run_import(old)['data']
        self.assertEqual(reused['snapshot_id'], first['snapshot_id'])
        self.assertEqual(reused['head_snapshot_id'], second['snapshot_id'])

    def test_selection_is_saved_without_becoming_head(self):
        original = self.feishu()
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['capture_scope'] = {'kind': 'selection', 'locator': {'paragraph': 1}}
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request)
        self.assertEqual(caught.exception.code, 'PARTIAL_CAPTURE_CANNOT_ADVANCE_HEAD')
        request['advance_head'] = False
        selected = self.run_import(request)['data']
        self.assertEqual(selected['head_snapshot_id'], first['snapshot_id'])
        self.assertNotEqual(selected['snapshot_id'], first['snapshot_id'])

    def test_stale_append_base_is_rejected(self):
        original = self.oral()
        first = self.run_import(original)['data']
        request = self.append(original, first)
        request['snapshot']['body']['text'] = '第二版'
        self.run_import(request)
        request['snapshot']['body']['text'] = '第三版'
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request)
        self.assertEqual(caught.exception.code, 'BASE_REVISION_CONFLICT')

    def test_local_bytes_are_copied_and_duplicate_requires_explicit_identity(self):
        request, path = self.local()
        content = path.read_bytes()
        first = self.run_import(request)['data']
        sha = hashlib.sha256(content).hexdigest()
        stored = self.root / 'yu-data' / 'objects' / 'sha256' / sha[:2] / sha
        path.unlink()
        self.assertEqual(stored.read_bytes(), content)
        self.assertEqual(first['assets'][0]['sha256'], sha)
        request2, path = self.local()
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request2)
        self.assertEqual(caught.exception.code, 'SOURCE_DUPLICATE')
        request2['target']['provider_key'] = 'explicit_second_source'
        second = self.run_import(request2)['data']
        self.assertNotEqual(second['source_id'], first['source_id'])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM blobs').fetchone()[0], 1)

    def test_hash_mismatch_commits_no_source(self):
        request, _ = self.local()
        request['snapshot']['assets'][0]['expected_sha256'] = '0' * 64
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request)
        self.assertEqual(caught.exception.code, 'FILE_HASH_MISMATCH')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM sources').fetchone()[0], 0)

    def test_external_asset_is_recorded_but_never_replaced_by_changed_bytes(self):
        request, path = self.local(storage='external')
        result = self.run_import(request)['data']
        path.write_text('new bytes')
        from yuplus.source import show_source
        shown = show_source(self.app.db, self.pid, result['source_id'])
        self.assertEqual(shown['snapshot']['assets'][0]['availability'], 'changed')
        self.assertEqual(shown['snapshot']['assets'][0]['sha256'], result['assets'][0]['sha256'])

    def test_idempotent_replay_does_not_reread_deleted_file(self):
        request, path = self.local()
        first = self.run_import(request, 'req_replay')
        path.unlink()
        replayed = self.run_import(request, 'req_replay')
        self.assertTrue(replayed['meta']['replayed'])
        self.assertEqual(replayed['data'], first['data'])

    def test_web_stable_identity_is_not_replaced_by_the_link(self):
        request = self.oral()
        request['target'] = {'mode': 'create', 'provider': 'web', 'resource_type': 'document',
                             'provider_key': 'archive:resource_17',
                             'canonical_url': 'https://example.com/current'}
        self.run_import(request)
        request['target']['canonical_url'] = 'https://example.com/renamed'
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request)
        self.assertEqual(caught.exception.code, 'SOURCE_EXISTS')

    def test_identical_bytes_in_another_project_have_independent_source_identity(self):
        request, _ = self.local()
        first = self.run_import(request)['data']
        second_pid = self.app.execute('project.create', {'name': '第二项目'}, request_id='req_another')['data']['project_id']
        second = self.run_import(request, project_id=second_pid)['data']
        self.assertNotEqual(first['source_id'], second['source_id'])
        self.assertEqual(first['assets'][0]['sha256'], second['assets'][0]['sha256'])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM blobs').fetchone()[0], 1)

    def test_partial_file_preparation_failure_keeps_no_database_capture(self):
        request, _ = self.local()
        missing = deepcopy(request['snapshot']['assets'][0])
        missing.update(asset_id='asset_missing', local_path=str(self.root / 'missing.pdf'))
        request['snapshot']['assets'].append(missing)
        with self.assertRaises(self.YuError) as caught:
            self.run_import(request)
        self.assertEqual(caught.exception.code, 'FILE_NOT_FOUND')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM sources').fetchone()[0], 0)
        self.assertEqual(list((self.root / 'yu-data' / 'staging').iterdir()), [])
        request['snapshot']['assets'].pop()
        self.assertEqual(self.run_import(request)['data']['snapshot_version'], 1)

    def test_feishu_type_aliases_resolve_to_one_persisted_source(self):
        from yuplus.source import show_source
        for canonical_type, alias in [('doc', 'docs'), ('sheet', 'sheets'), ('bitable', 'base')]:
            with self.subTest(resource_type=canonical_type):
                request = self.feishu()
                request['target']['resource_type'] = alias
                request['target']['canonical_url'] = f'https://example.feishu.cn/{alias}/docx_demo'
                first = self.run_import(request)['data']
                shown = show_source(self.app.db, self.pid, first['source_id'])
                self.assertEqual(shown['resource_type'], canonical_type)
                request['target']['resource_type'] = canonical_type
                with self.assertRaises(self.YuError) as caught:
                    self.run_import(request)
                self.assertEqual(caught.exception.code, 'SOURCE_EXISTS')

    def test_external_to_copy_creates_manifest_version_without_changing_content_hash(self):
        from yuplus.source import show_source
        for provider_revision in [None, '17']:
            with self.subTest(provider_revision=provider_revision):
                request, path = self.local(storage='external', explicit_key=f'origin_{provider_revision}')
                request['snapshot']['provider_revision'] = provider_revision
                first = self.run_import(request)['data']
                old = show_source(self.app.db, self.pid, first['source_id'])['snapshot']
                update = self.append(request, first)
                update['snapshot']['assets'][0]['storage'] = 'copy'
                second = self.run_import(update)['data']
                self.assertEqual(second['effect'], 'changed')
                self.assertEqual(second['snapshot_version'], 2)
                self.assertNotEqual(second['snapshot_id'], first['snapshot_id'])
                path.unlink()
                current = show_source(self.app.db, self.pid, first['source_id'])['snapshot']
                self.assertEqual(current['assets'][0]['storage'], 'copy')
                self.assertEqual(current['content_hash'], old['content_hash'])
                copied = self.root / 'yu-data' / 'objects' / current['assets'][0]['storage_key']
                self.assertTrue(copied.is_file())
                original = show_source(self.app.db, self.pid, first['source_id'], first['snapshot_id'])['snapshot']
                self.assertEqual(original['assets'][0]['storage'], 'external')
                self.assertEqual(original['assets'][0]['availability'], 'missing')

    def test_external_path_change_preserves_old_manifest_and_new_path(self):
        from yuplus.source import show_source
        request, path = self.local(storage='external')
        first = self.run_import(request)['data']
        moved = self.root / 'moved.pdf'
        path.rename(moved)
        update = self.append(request, first)
        update['snapshot']['assets'][0]['local_path'] = str(moved)
        second = self.run_import(update)['data']
        self.assertEqual(second['snapshot_version'], 2)
        current = show_source(self.app.db, self.pid, first['source_id'])['snapshot']
        self.assertEqual(current['assets'][0]['local_path'], str(moved.resolve()))
        self.assertEqual(current['assets'][0]['availability'], 'available')
        old = show_source(self.app.db, self.pid, first['source_id'], first['snapshot_id'])['snapshot']
        self.assertEqual(old['assets'][0]['availability'], 'missing')
        repeat = self.run_import(self.append(update, second))['data']
        self.assertEqual(repeat['effect'], 'noop')
        self.assertEqual(repeat['snapshot_id'], second['snapshot_id'])

    def test_copy_input_path_change_does_not_create_a_manifest_version(self):
        request, path = self.local()
        first = self.run_import(request)['data']
        moved = self.root / 'moved.pdf'
        path.rename(moved)
        update = self.append(request, first)
        update['snapshot']['assets'][0]['local_path'] = str(moved)
        repeated = self.run_import(update)['data']
        self.assertEqual(repeated['effect'], 'noop')
        self.assertEqual(repeated['snapshot_id'], first['snapshot_id'])

    def test_old_remote_revision_cannot_regain_head_through_storage_change(self):
        request, _ = self.local(storage='external')
        request['snapshot']['provider_revision'] = '17'
        first = self.run_import(request)['data']
        update = self.append(request, first)
        update['snapshot']['provider_revision'] = '18'
        second = self.run_import(update)['data']
        old = self.append(request, second)
        old['snapshot']['assets'][0]['storage'] = 'copy'
        with self.assertRaises(self.YuError) as caught:
            self.run_import(old)
        self.assertEqual(caught.exception.code, 'SOURCE_REVISION_OUTDATED')

    def test_append_cannot_reference_another_projects_source(self):
        original = self.oral()
        first = self.run_import(original)['data']
        second_pid = self.app.execute('project.create', {'name': '另一项目'}, request_id='req_project2')['data']['project_id']
        with self.assertRaises(self.YuError) as caught:
            self.run_import(self.append(original, first), project_id=second_pid)
        self.assertEqual(caught.exception.code, 'CROSS_PROJECT_REFERENCE')


if __name__ == '__main__':
    unittest.main()
