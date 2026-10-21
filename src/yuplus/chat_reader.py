"""User-only, read-only lark-cli adapter with explicit one-page completeness.

The runner has subprocess.run's interface. Credentials are managed by lark-cli;
this module never reads credential files or logs raw command output. A reader
pins the nonsecret user open ID, checking it before and after every remote read.
"""
from __future__ import annotations

import copy
from datetime import datetime
import json
import os
import re
import subprocess
from urllib.parse import parse_qs, urlsplit

from .core import YuError


def _fail(message='飞书返回的数据不完整或格式无法识别。'):
    raise YuError('FEISHU_UNAVAILABLE', message)


def _identifier(value, prefixes, *, remote=False):
    pattern = r'(?:' + '|'.join(prefixes) + r')_[A-Za-z0-9_-]+'
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        if remote:
            _fail()
        raise YuError('INVALID_INPUT', '飞书群聊、话题或消息标识无效。')
    return value


def _time(value, *, bound=False):
    """Validate without replacing the provider's original timestamp."""
    try:
        if not bound and ((type(value) is int and value >= 0) or
                          (isinstance(value, str) and value.isascii() and value.isdigit())):
            return int(value) / 1000
        if not isinstance(value, str):
            raise ValueError
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError
        return stamp.timestamp()
    except (ValueError, TypeError, OverflowError):
        if bound:
            raise YuError('INVALID_INPUT', '消息时间范围必须是带时区的 ISO 时间。') from None
        _fail('飞书消息缺少可识别的创建时间。')


class FeishuChatReader:
    def __init__(self, runner=None):
        self.runner = runner or subprocess.run
        self._principal = None

    def _execute(self, args, *, auth=False):
        env = {**os.environ, 'LARKSUITE_CLI_NO_UPDATE_NOTIFIER': '1',
               'LARKSUITE_CLI_NO_SKILLS_NOTIFIER': '1'}
        try:
            result = self.runner(['lark-cli', *args], env=env, stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            raise YuError('FEISHU_UNAVAILABLE', '飞书 CLI 不可用或读取超时。') from None
        if result.returncode != 0:
            _fail('飞书读取未成功，请按 lark-shared 检查认证与权限。')
        try:
            value = json.loads(result.stdout)
        except (ValueError, TypeError):
            _fail()
        if not isinstance(value, dict):
            _fail()
        # auth status is also emitted as a bare status object by CLI versions.
        # Only that command accepts it; every IM read requires the full envelope.
        if auth and 'ok' not in value:
            data, meta = value, {}
        else:
            if value.get('ok') is not True or value.get('identity') != 'user':
                _fail('飞书读取未返回当前用户身份的成功结果。')
            data, meta = value.get('data'), value.get('meta', {})
        if not isinstance(data, dict) or not isinstance(meta, dict):
            _fail()
        for container in (value, data, meta):
            if any(container.get(key) for key in ('error', 'errors', 'truncated', 'truncations')):
                _fail('飞书返回错误或截断结果，不能确认读取完整。')
        return data, meta

    def _check_identity(self):
        data, _ = self._execute(['auth', 'status', '--json'], auth=True)
        if data.get('identity') != 'user':
            _fail('群聊监控需要已登录的飞书用户身份。')
        identities = data.get('identities')
        user = identities.get('user') if isinstance(identities, dict) else None
        principal = user.get('openId') if isinstance(user, dict) else None
        _identifier(principal, ['ou'], remote=True)
        if self._principal is not None and self._principal != principal:
            raise YuError('FEISHU_IDENTITY_CHANGED', '飞书用户身份已变化，请重新核验群聊绑定。')
        self._principal = principal
        return principal

    def _read(self, args):
        self._check_identity()
        data, meta = self._execute([*args, '--as', 'user', '--format', 'json'])
        self._check_identity()
        return data, meta

    def info(self, chat_id):
        _identifier(chat_id, ['oc'])
        data, _ = self._read(['im', 'chats', 'get', '--params', json.dumps({'chat_id': chat_id})])
        if 'chat_id' in data and data['chat_id'] != chat_id:
            _fail('飞书返回的群聊身份与请求不符。')
        tenant = data.get('tenant_key')
        if not isinstance(tenant, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', tenant):
            _fail('飞书未返回可核验的群聊租户范围。')
        name = data.get('name')
        if name is not None and not isinstance(name, str):
            _fail()
        url = f'https://applink.feishu.cn/client/chat/open?openChatId={chat_id}'
        supplied = data.get('chat_app_link')
        if isinstance(supplied, str):
            try:
                parts = urlsplit(supplied)
            except ValueError:
                parts = None
            if (parts is not None and parts.scheme == 'https'
                    and parts.netloc in {'applink.feishu.cn', 'applink.larksuite.com'}
                    and parts.path == '/client/chat/open'
                    and parse_qs(parts.query).get('openChatId') == [chat_id]):
                url = supplied
        return {'chat_id': chat_id, 'name': name or chat_id, 'url': url,
                'identity': f'feishu:user:{tenant}:{self._principal}'}

    def messages(self, chat_id, start, end, page_token=None):
        _identifier(chat_id, ['oc'])
        begin = _time(start, bound=True) if start is not None else None
        finish = _time(end, bound=True) if end is not None else None
        if begin is not None and finish is not None and begin > finish:
            raise YuError('INVALID_INPUT', '消息开始时间不能晚于结束时间。')
        args = ['im', '+chat-messages-list', '--chat-id', chat_id]
        if start is not None:
            args += ['--start', start]
        if end is not None:
            args += ['--end', end]
        return self._page(args, page_token)

    def replies(self, thread_id, page_token=None):
        _identifier(thread_id, ['om', 'omt'])
        return self._page(['im', '+threads-messages-list', '--thread', thread_id], page_token)

    def _page(self, args, page_token):
        args += ['--order', 'asc', '--page-size', '50']
        if page_token is not None:
            if not isinstance(page_token, str) or not page_token or '\x00' in page_token:
                raise YuError('INVALID_INPUT', '分页游标无效。')
            args += ['--page-token', page_token]
        data, meta = self._read(args)
        messages = self._messages(data)
        more, token = data.get('has_more'), data.get('page_token')
        if type(more) is not bool or (token is not None and not isinstance(token, str)):
            _fail()
        if more and (not token or token == page_token or '\x00' in token):
            _fail('飞书分页缺少有效的后续游标。')
        pagination = meta.get('pagination')
        if 'pagination' in meta:
            if not isinstance(pagination, dict):
                _fail()
            complete = pagination.get('complete')
            if type(complete) is not bool or complete == more:
                _fail('飞书分页完整性标记不一致。')
            if more and pagination.get('next_token', token) != token:
                _fail('飞书分页游标不一致。')
        messages.sort(key=lambda item: (_time(item['create_time']), item['message_id']))
        return {'messages': messages, 'has_more': more, 'page_token': token if more else None}

    @staticmethod
    def _messages(data):
        messages = data.get('messages')
        if not isinstance(messages, list):
            _fail()
        if 'total' in data and (type(data['total']) is not int or data['total'] != len(messages)):
            _fail('飞书返回的消息数量不一致。')

        def validate(message, depth=0):
            if depth > 32 or not isinstance(message, dict):
                _fail()
            _identifier(message.get('message_id'), ['om'], remote=True)
            _time(message.get('create_time'))
            if not isinstance(message.get('content'), str):
                _fail('飞书消息缺少原始正文。')
            if 'sender' in message and not isinstance(message['sender'], dict):
                _fail()
            for flag in ('deleted', 'updated', 'thread_has_more', 'thread_replies_error'):
                if flag in message and type(message[flag]) is not bool:
                    _fail()
            if message.get('thread_id'):
                _identifier(message['thread_id'], ['om', 'omt'], remote=True)
            if (message.get('thread_has_more') or message.get('thread_replies_error')) and not message.get('thread_id'):
                _fail('飞书话题读取不完整且缺少话题标识。')
            if 'thread_replies' in message:
                if not isinstance(message['thread_replies'], list):
                    _fail()
                for reply in message['thread_replies']:
                    validate(reply, depth + 1)
        for message in messages:
            validate(message)
        if len({message['message_id'] for message in messages}) != len(messages):
            _fail('飞书单页返回重复的消息标识。')
        return copy.deepcopy(messages)

    def details(self, message_ids):
        if not isinstance(message_ids, (list, tuple)) or len(message_ids) > 50:
            raise YuError('INVALID_INPUT', '单次消息详情查询最多支持 50 条消息。')
        for message_id in message_ids:
            _identifier(message_id, ['om'])
        if len(set(message_ids)) != len(message_ids):
            raise YuError('INVALID_INPUT', '消息详情查询不能包含重复标识。')
        if not message_ids:
            return []
        data, meta = self._read(['im', '+messages-mget', '--message-ids', ','.join(message_ids)])
        messages = self._messages(data)
        pagination = meta.get('pagination', {})
        if not isinstance(pagination, dict) or ('pagination' in meta and pagination.get('complete') is not True):
            _fail('飞书消息详情完整性标记无效。')
        if 'has_more' in data and data['has_more'] is not False:
            _fail('飞书消息详情结果不完整。')
        if {message['message_id'] for message in messages} != set(message_ids):
            _fail('飞书未返回全部请求的消息，缺失不能视为撤回。')
        return messages
