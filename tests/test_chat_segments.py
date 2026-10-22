"""Conversation units preserve member evidence without flooding the source library."""
import json
from yuplus.core import YuError, now
from yuplus.source_check import scan
import unittest
from tests import test_monitor as fixtures


class ChatSegmentTests(unittest.TestCase):
    setUp=fixtures.MonitorTests.setUp
    begin=fixtures.MonitorTests.begin
    call=fixtures.MonitorTests.call
    draft=fixtures.MonitorTests.draft
    def test_segment_capture_one_source_with_all_turns_and_retry(self):
        auth=self.begin();self.call('fetch',{**auth,'page_budget':10})
        rows=self.call('pending',auth)['messages'];ids=[r['id'] for r in rows]
        request={**auth,'message_versions':ids[::-1],'title':'预算调整讨论 · 100万至60万'}
        result=self.call('capture',request)
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM sources').fetchone()[0],1)
        source=self.app.execute('source.show',{'source_id':result['source_id'],'include_body':True},project_id=self.pid)['data']
        self.assertEqual(source['resource_type'],'chat_segment')
        body=source['snapshot']['body']['text']
        self.assertLess(body.index('预算100万'),body.index('确认'))
        self.assertLess(body.index('确认'),body.index('预算60万'))
        self.assertIn('甲方',body);self.assertIn('openChatId=oc_test',body)
        replay=self.call('capture',{**request,'message_versions':ids})
        self.assertTrue(replay['reused']);self.assertEqual(replay['source_version_id'],result['source_version_id'])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM source_versions').fetchone()[0],1)
        with self.assertRaises(YuError):self.call('capture',{**request,'title':'改了标题'})
        # Use one grouped source for an adopted decision and all affected turns.
        draft=self.call('step',{**auth,'message_versions':ids,'step_key':'budget_segment','command':'draft.apply',
                               'input':self.draft(result['source_version_id'],'60000000')})
        self.call('resolve',{**auth,'message_versions':ids,'outcome':'applied','reason':'讨论明确预算调整','change_ids':[draft['meta']['change_id']]})
        self.call('finish',{**auth,'summary':'一次讨论形成一个信源和业务决定'})
        # Referenced non-anchor members must still be included in daily rechecks.
        self.app.db.execute('UPDATE chat_monitors SET last_recheck_at=NULL WHERE id=?',(self.mon,))
        later=self.begin()
        cursor=json.loads(self.app.db.execute('SELECT cursor_json FROM monitor_runs WHERE id=?',(later['run_id'],)).fetchone()[0])
        self.assertEqual(set(cursor['recheck_ids']),{r['message_id'] for r in rows})
        checked=scan(self.app.data_dir,self.pid,observer=lambda s:self.fail('chat segment is not a document'))
        self.assertEqual(checked['checks'],[])
        with self.assertRaises(YuError) as err:scan(self.app.data_dir,self.pid,result['source_id'])
        self.assertEqual(err.exception.code,'SOURCE_CHECK_UNSUPPORTED')

    def test_segment_requires_title_valid_unique_members_and_project_scope(self):
        auth=self.begin();self.call('fetch',{**auth,'page_budget':10})
        vid=self.call('pending',auth)['messages'][0]['id']
        for payload in [{'message_versions':[vid]}, {'message_versions':[vid,vid],'title':'主题'},
                        {'message_versions':['missing'],'title':'主题'},
                        {'message_versions':[vid],'message_version':vid,'title':'主题'}]:
            with self.subTest(payload=payload),self.assertRaises(YuError):self.call('capture',{**auth,**payload})
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM sources').fetchone()[0],0)

