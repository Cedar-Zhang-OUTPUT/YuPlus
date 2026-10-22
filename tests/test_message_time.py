"""Remote times retain their meaning across process timezones and input forms."""
from contextlib import contextmanager
import os
import time
import unittest
from unittest.mock import patch

from yuplus.chat_reader import FeishuChatReader, _time
from yuplus.core import YuError
from yuplus.monitor import instant
from tests.test_chat_reader import Runner, envelope, message


@contextmanager
def local_zone(name):
    try:
        with patch.dict(os.environ, {'TZ': name}):
            time.tzset()
            yield
    finally:
        time.tzset()



class MessageTimeTests(unittest.TestCase):
    def test_local_minutes_seconds_and_explicit_offsets_agree(self):
        with local_zone('Asia/Shanghai'):
            for value in ['2025-12-11 14:52', '2025-12-11 14:52:00',
                          '2025-12-11T14:52:00+08:00', '2025-12-11T06:52:00Z']:
                with self.subTest(value=value):
                    self.assertEqual(instant(value), '2025-12-11T06:52:00.000000Z')
                    self.assertEqual(_time(value), _time('2025-12-11T06:52:00Z'))
            milliseconds=int(_time('2025-12-11 14:52') * 1000)
            self.assertEqual(instant(milliseconds), instant(str(milliseconds)))
            self.assertEqual(instant(milliseconds), instant('2025-12-11 14:52'))
            self.assertEqual(instant('2025-12-11 14:52:03.123'), '2025-12-11T06:52:03.123000Z')

    def test_local_zone_uses_historical_dst_not_current_offset(self):
        with local_zone('America/New_York'):
            self.assertEqual(instant('2025-07-11 14:52'), '2025-07-11T18:52:00.000000Z')
            self.assertEqual(instant('2025-12-11 14:52'), '2025-12-11T19:52:00.000000Z')
        with local_zone('UTC'):
            self.assertEqual(instant('2025-12-11 14:52'), '2025-12-11T14:52:00.000000Z')

    def test_bad_values_still_fail_and_window_bounds_require_offsets(self):
        for value in [None, True, -1, 1.5, 'bad', '2025-02-30 14:52',
                      '2025-12-11', '2025-12-11T14:52', '2025-12-11 25:00', '9' * 100]:
            with self.subTest(value=value):
                with self.assertRaises(YuError):instant(value)
                with self.assertRaises(YuError):_time(value)
        with self.assertRaises(YuError):_time('2025-12-11 14:52', bound=True)

    def test_reader_sorts_mixed_formats_and_retains_original_evidence(self):
        rows=[message('om_later',create_time='2025-12-11 14:53'),
              message('om_first',create_time='2025-12-11T06:51:00Z',
                      thread_replies=[message('om_reply',create_time='2025-12-11 14:51:30')]),
              message('om_middle',create_time='2025-12-11 14:52',update_time='2025-12-11 15:00')]
        with local_zone('Asia/Shanghai'):
            reader=FeishuChatReader(Runner(envelope({'messages':rows,'has_more':False})))
            page=reader.messages('oc_project',None,'2025-12-12T00:00:00Z')
        self.assertEqual([m['message_id'] for m in page['messages']],['om_first','om_middle','om_later'])
        self.assertEqual(page['messages'][1],rows[2])
