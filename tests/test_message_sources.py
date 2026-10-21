"""Message evidence uses stable scoped identities and never document scanners."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from yuplus.app import App
from yuplus.core import YuError
from yuplus.source import show_source
from yuplus.source_check import scan


class MessageSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = App(self.root)
        self.addCleanup(self.app.close)
        self.pid = self.app.execute('project.create', {'name': '消息项目'}, request_id='req_project')['data']['project_id']
        self.sequence = 0

    def request(self, url=None, key=None):
        return {'api_version': '1', 'command': 'source.import',
                'target': {'mode': 'create', 'provider': 'feishu', 'resource_type': 'message',
                           'provider_key': key or 'feishu:user:tenant_one:ou_reader:oc_project:om_one',
                           'canonical_url': url or 'https://applink.feishu.cn/client/chat/open?openChatId=oc_project'},
                'snapshot': {'title': '项目群 · 发言人 · 2026-10-21', 'provider_revision': None,
                             'captured_at': '2026-10-21T00:00:00Z',
                             'capture_scope': {'kind': 'whole_resource'}, 'extraction_profile': 'feishu-message-v1',
                             'body': {'format': 'text', 'text': '原始消息。'},
                             'provenance': {'method': 'lark-cli-message', 'reported_by': '发言人'}},
                'advance_head': True, 'reason': '保存群消息原文'}

    def execute(self, request, pid=None):
        self.sequence += 1
        return self.app.execute('source.import', request, project_id=pid or self.pid,
                                request_id=f'req_message_{self.sequence}')['data']

    def test_message_identity_and_navigation_query_survive_import(self):
        urls = [
            'https://applink.feishu.cn/client/chat/open?openChatId=oc_project',
            'https://applink.larksuite.com/client/chat/open?openChatId=oc_project&position=0',
            'https://applink.feishu.cn/client/thread/open?openchatid=oc_project&open_chat_id=oc_project&openthreadid=omt_topic&open_thread_id=omt_topic&thread_position=-2',
        ]
        for i, url in enumerate(urls):
            request = self.request(url, f'feishu:user:tenant_one:ou_reader:oc_project:om_{i}')
            result = self.execute(request)
            self.assertEqual(result['canonical_url'], url)
            source = show_source(self.app.db, self.pid, result['source_id'])
            self.assertEqual(source['provider_key'], request['target']['provider_key'])
            self.assertEqual(source['snapshot']['body']['text'], '原始消息。')

    def test_unsafe_or_ambiguous_message_links_rejected_without_writes(self):
        urls = [
            'https://evil.feishu.cn/client/chat/open?openChatId=oc_project',
            'https://applink.feishu.cn.evil.example/client/chat/open?openChatId=oc_project',
            'https://applink.feishu.cn:8443/client/chat/open?openChatId=oc_project',
            'https://name@applink.feishu.cn/client/chat/open?openChatId=oc_project',
            'http://applink.feishu.cn/client/chat/open?openChatId=oc_project',
            'https://applink.feishu.cn/client/chat/open?openChatId=oc_other',
            'https://applink.feishu.cn/client/chat/open?openChatId=oc_project&openChatId=oc_other',
            'https://applink.feishu.cn/client/chat/open?openChatId=oc_project&redirect=https://evil.example',
            'https://applink.feishu.cn/client/chat/open?openChatId=oc_project&position=NaN',
            'https://applink.feishu.cn/client/thread/open?openchatid=oc_project&open_chat_id=oc_other&openthreadid=omt_topic&thread_position=1',
            'https://applink.feishu.cn/client/message/link/open?token=opaque',
            'https://applink.feishu.cn/docx/docx_doc',
            'https://[invalid',
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(YuError) as raised:
                self.execute(self.request(url))
            self.assertEqual(raised.exception.code, 'INVALID_INPUT')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM sources').fetchone()[0], 0)

    def test_message_key_requires_namespace_chat_and_message(self):
        for key in ['om_one', 'oc_project:om_one', 'tenant:oc_other:om_one',
                    'tenant:oc_project:docx_one', 'tenant:oc_project:om_one:extra']:
            with self.subTest(key=key), self.assertRaises(YuError):
                self.execute(self.request(key=key))

    def test_document_link_validation_is_not_relaxed(self):
        request = self.request()
        request['target']['resource_type'] = 'docx'
        request['target']['provider_key'] = 'tenant:docx_one'
        with self.assertRaises(YuError):
            self.execute(request)
        request['target']['canonical_url'] = 'https://project.feishu.cn/docx/docx_one?from=copy#heading'
        result = self.execute(request)
        self.assertEqual(result['canonical_url'], 'https://project.feishu.cn/docx/docx_one')

    def test_manual_capture_reuses_identity_and_append_keeps_immutable_versions(self):
        original = self.request()
        first = self.execute(original)
        with self.assertRaises(YuError) as raised:
            self.execute(original)
        self.assertEqual(raised.exception.code, 'SOURCE_EXISTS')
        append = deepcopy(original)
        append['target'] = {'mode': 'append', 'source_id': first['source_id'], 'base_snapshot_id': first['head_snapshot_id']}
        unchanged = self.execute(append)
        self.assertEqual(unchanged['snapshot_id'], first['snapshot_id'])
        append['snapshot']['body']['text'] = '修改后的消息。'
        second = self.execute(append)
        self.assertEqual(second['snapshot_version'], 2)
        self.assertEqual(show_source(self.app.db, self.pid, first['source_id'], first['snapshot_id'])['snapshot']['body']['text'], '原始消息。')
        with self.assertRaises(YuError) as stale:
            self.execute(append)
        self.assertEqual(stale.exception.code, 'BASE_REVISION_CONFLICT')

    def test_document_scan_excludes_message_sources_and_reports_targeted_unsupported(self):
        message = self.execute(self.request())
        doc = self.request('https://project.feishu.cn/docx/docx_one', 'tenant:docx_one')
        doc['target']['resource_type'] = 'docx'
        doc['snapshot']['provider_revision'] = '1'
        document = self.execute(doc)
        observed = []
        def observer(source):
            observed.append(source['id'])
            return {'marker': '1', 'kind': 'revision'}
        result = scan(self.root, self.pid, observer=observer)
        self.assertEqual(observed, [document['source_id']])
        self.assertEqual(len(result['checks']), 1)
        row = self.app.db.execute('SELECT last_checked_at,observation_generation FROM sources WHERE id=?', (message['source_id'],)).fetchone()
        self.assertIsNone(row['last_checked_at'])
        with self.assertRaises(YuError) as raised:
            scan(self.root, self.pid, message['source_id'], observer=observer)
        self.assertEqual(raised.exception.code, 'SOURCE_CHECK_UNSUPPORTED')
        self.assertEqual(observed, [document['source_id']])


if __name__ == '__main__':
    unittest.main()
