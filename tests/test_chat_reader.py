"""Read adapter contract: subprocess fixtures only, never a live Feishu account."""
import copy
import json
import subprocess
import unittest

from yuplus.core import YuError
from yuplus.chat_reader import FeishuChatReader


def message(ident='om_one', **fields):
    return {'message_id': ident, 'create_time': '2026-10-20T12:00:00+08:00',
            'msg_type': 'text', 'content': '原文', 'sender': {'id': 'ou_sender', 'name': '发言人'},
            'deleted': False, 'updated': False, **fields}


def envelope(data, **fields):
    return {'ok': True, 'identity': 'user', 'data': data, **fields}


class Runner:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.status = {'identity': 'user', 'identities': {'user': {'openId': 'ou_reader'}}}

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if argv[1:3] == ['auth', 'status']:
            value = copy.deepcopy(self.status)
        else:
            value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, subprocess.CompletedProcess):
            return value
        return subprocess.CompletedProcess(argv, 0, json.dumps(value), '')


class ChatReaderTests(unittest.TestCase):
    def test_info_binds_nonsecret_principal_and_tenant(self):
        runner = Runner(envelope({'name': '项目群', 'tenant_key': 'tenant_one'}))
        runner.status['accessToken'] = 'SECRET_DO_NOT_PERSIST'
        info = FeishuChatReader(runner).info('oc_project')
        self.assertEqual(info['chat_id'], 'oc_project')
        self.assertEqual(info['name'], '项目群')
        self.assertEqual(info['url'], 'https://applink.feishu.cn/client/chat/open?openChatId=oc_project')
        self.assertEqual(info['identity'], 'feishu:user:tenant_one:ou_reader')
        self.assertNotIn('SECRET', json.dumps(info))
        call = next(argv for argv, _ in runner.calls if argv[1] == 'im')
        self.assertEqual(call[1:4], ['im', 'chats', 'get'])
        self.assertEqual(json.loads(call[call.index('--params') + 1]), {'chat_id': 'oc_project'})

    def test_first_history_has_no_lower_bound_and_preserves_thread_evidence(self):
        root = message(thread_id='omt_topic', thread_has_more=True,
                       thread_replies_error=True, thread_replies=[message('om_reply')],
                       update_time='1792483200000', mentions=[{'id': 'ou_other'}])
        runner = Runner(envelope({'messages': [root], 'has_more': True, 'page_token': 'next', 'total': 1}))
        page = FeishuChatReader(runner).messages('oc_project', None, '2026-10-21T00:00:00Z')
        self.assertEqual(page, {'messages': [root], 'has_more': True, 'page_token': 'next'})
        argv, kwargs = next(call for call in runner.calls if call[0][1] == 'im')
        self.assertNotIn('--start', argv)
        self.assertNotIn('--page-all', argv)
        self.assertNotIn('--no-reactions', argv)  # Keep edit-time enrichment.
        self.assertEqual(argv[argv.index('--end') + 1], '2026-10-21T00:00:00Z')
        self.assertEqual(argv[argv.index('--order') + 1], 'asc')
        self.assertEqual(argv[argv.index('--as') + 1], 'user')
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.assertNotIn('shell', kwargs)

    def test_incremental_range_and_opaque_cursor_are_individual_argv_entries(self):
        runner = Runner(envelope({'messages': [], 'has_more': False}))
        token = 'opaque; $(touch injected) & "quoted"'
        page = FeishuChatReader(runner).messages('oc_project', '2026-10-20T00:00:00Z',
                                               '2026-10-21T00:00:00Z', token)
        argv = next(argv for argv, _ in runner.calls if argv[1] == 'im')
        self.assertEqual(argv[argv.index('--page-token') + 1], token)
        self.assertEqual(argv[argv.index('--start') + 1], '2026-10-20T00:00:00Z')
        self.assertFalse(page['has_more'])
        self.assertIsNone(page['page_token'])

    def test_replies_ascending_without_unsupported_time_filters(self):
        runner = Runner(envelope({'messages': [message()], 'has_more': False, 'page_token': 'last'}))
        page = FeishuChatReader(runner).replies('omt_topic', 'cursor')
        argv = next(argv for argv, _ in runner.calls if argv[1] == 'im')
        self.assertIn('+threads-messages-list', argv)
        self.assertEqual(argv[argv.index('--thread') + 1], 'omt_topic')
        self.assertEqual(argv[argv.index('--order') + 1], 'asc')
        self.assertNotIn('--start', argv)
        self.assertNotIn('--end', argv)
        self.assertIsNone(page['page_token'])  # A final-page cursor is not another page.

    def test_page_failure_and_truncation_never_become_empty_success(self):
        bad_pages = [
            {'ok': False, 'error': {'message': 'SECRET'}},
            {'code': 0, 'data': {'messages': []}},
            envelope({'messages': [], 'has_more': False}, identity='bot'),
            envelope({'messages': []}),
            envelope({'messages': [], 'has_more': 'false'}),
            envelope({'messages': [], 'has_more': True}),
            envelope({'messages': [], 'has_more': False, 'truncated': True}),
            envelope({'messages': [], 'has_more': False}, meta={'pagination': {'complete': False}}),
            envelope({'messages': [], 'has_more': False, 'errors': ['SECRET']}),
            envelope({'messages': [], 'has_more': False, 'total': 1}),
            envelope({'messages': [message(content=None)], 'has_more': False}),
            envelope({'messages': [message(create_time='bad')], 'has_more': False}),
            envelope({'messages': [message(thread_replies=[{}])], 'has_more': False}),
        ]
        for bad in bad_pages:
            with self.subTest(bad=bad), self.assertRaises(YuError) as raised:
                FeishuChatReader(Runner(bad)).messages('oc_project', None, None)
            self.assertNotIn('SECRET', str(raised.exception))

    def test_resumable_pagination_metadata_is_not_silently_dropped(self):
        runner = Runner(envelope({'messages': [], 'has_more': True, 'page_token': 'next'},
                                 meta={'pagination': {'complete': False, 'next_token': 'next'}}))
        self.assertEqual(FeishuChatReader(runner).replies('omt_topic')['page_token'], 'next')
        for meta in [{'complete': False, 'next_token': 'different'}, {'complete': True}]:
            with self.subTest(meta=meta), self.assertRaises(YuError):
                FeishuChatReader(Runner(envelope({'messages': [], 'has_more': True, 'page_token': 'next'},
                                                meta={'pagination': meta}))).replies('omt_topic')

    def test_repeated_cursor_is_failure(self):
        reader = FeishuChatReader(Runner(envelope({'messages': [], 'has_more': True, 'page_token': 'same'})))
        with self.assertRaises(YuError):
            reader.replies('omt_topic', 'same')

    def test_bad_identity_and_identity_switch_are_rejected(self):
        for status in [{'identity': 'bot', 'identities': {'user': {'openId': 'ou_reader'}}},
                       {'identity': 'user', 'identities': {'user': {}}}]:
            runner = Runner()
            runner.status = status
            with self.subTest(status=status), self.assertRaises(YuError):
                FeishuChatReader(runner).messages('oc_project', None, None)
            self.assertFalse(any(argv[1] == 'im' for argv, _ in runner.calls))
        runner = Runner(envelope({'messages': [], 'has_more': False}))
        reader = FeishuChatReader(runner)
        reader.messages('oc_project', None, None)
        runner.status['identities']['user']['openId'] = 'ou_changed'
        with self.assertRaises(YuError) as raised:
            reader.messages('oc_project', None, None)
        self.assertEqual(raised.exception.code, 'FEISHU_IDENTITY_CHANGED')

    def test_details_missing_or_duplicate_ids_do_not_mean_recall(self):
        for messages in [[], [message('om_other')], [message(), message()]]:
            with self.subTest(messages=messages), self.assertRaises(YuError):
                FeishuChatReader(Runner(envelope({'messages': messages}))).details(['om_one'])
        recalled = message(deleted=True, content='')
        runner = Runner(envelope({'messages': [recalled], 'total': 1}))
        self.assertEqual(FeishuChatReader(runner).details(['om_one']), [recalled])
        argv = next(argv for argv, _ in runner.calls if argv[1] == 'im')
        self.assertEqual(argv[argv.index('--message-ids') + 1], 'om_one')

    def test_invalid_input_never_starts_process(self):
        runner = Runner()
        reader = FeishuChatReader(runner)
        bad_calls = [lambda: reader.info('oc_a;evil'), lambda: reader.replies('--help'),
                     lambda: reader.messages('oc_a', 'yesterday', None),
                     lambda: reader.messages('oc_a', '2026-10-21T00:00:00Z', '2026-10-20T00:00:00Z'),
                     lambda: reader.details(['om_x'] * 51), lambda: reader.details(['om_x', 'om_x'])]
        for call in bad_calls:
            with self.subTest(call=call), self.assertRaises(YuError):
                call()
        self.assertEqual(reader.details([]), [])
        self.assertFalse(runner.calls)

    def test_process_failure_does_not_echo_output_or_exception_secrets(self):
        failures = [FileNotFoundError('SECRET'), subprocess.TimeoutExpired('SECRET', 10),
                    subprocess.CompletedProcess([], 1, '', '{"ok":false,"error":{"message":"SECRET"}}'),
                    subprocess.CompletedProcess([], 0, 'SECRET invalid json', '')]
        for failure in failures:
            with self.subTest(failure=failure), self.assertRaises(YuError) as raised:
                FeishuChatReader(Runner(failure)).replies('omt_topic')
            self.assertNotIn('SECRET', str(raised.exception))

    def test_account_switch_during_request_rejects_the_returned_page(self):
        runner = Runner(envelope({'messages': [message()], 'has_more': False}))
        def switch_after_read(argv, **kwargs):
            result = runner(argv, **kwargs)
            if argv[1] == 'im':
                runner.status['identities']['user']['openId'] = 'ou_new_account'
            return result
        with self.assertRaises(YuError) as raised:
            FeishuChatReader(switch_after_read).messages('oc_project', None, None)
        self.assertEqual(raised.exception.code, 'FEISHU_IDENTITY_CHANGED')

    def test_details_reject_malformed_pagination_metadata(self):
        for pagination in [None, [], 'broken', {'complete': 'false'}]:
            runner = Runner(envelope({'messages': [message()]}, meta={'pagination': pagination}))
            with self.subTest(pagination=pagination), self.assertRaises(YuError):
                FeishuChatReader(runner).details(['om_one'])

    def test_bad_remote_link_uses_verified_chat_applink(self):
        runner = Runner(envelope({'name': '项目', 'tenant_key': 'tenant_one',
                                 'chat_app_link': 'https://[invalid'}))
        info = FeishuChatReader(runner).info('oc_project')
        self.assertEqual(info['url'], 'https://applink.feishu.cn/client/chat/open?openChatId=oc_project')


if __name__ == '__main__':
    unittest.main()
