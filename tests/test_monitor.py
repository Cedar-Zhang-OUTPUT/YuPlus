import copy
import tempfile
import unittest
from pathlib import Path
from yuplus.app import App
from yuplus.core import YuError
from yuplus.monitor import Monitor
from yuplus.core import now, canonical
from yuplus.backup import create_backup, restore_backup, verify_backup
import json
import sqlite3
from unittest.mock import patch
from yuplus.monitor import shifted

class FakeReader:
    def __init__(self): self.identity='feishu:user:tenant:ou_test'; self.calls=[]; self.fail=False
    def info(self, chat_id): return {'chat_id':chat_id,'name':'项目群','url':'https://applink.feishu.cn/client/chat/open?openChatId='+chat_id,'identity':self.identity}
    def messages(self, chat_id, start, end, page_token=None):
        self.calls.append((start,end,page_token))
        if self.fail: raise YuError('FEISHU_UNAVAILABLE','offline')
        if not page_token: return {'messages':[self.msg('om_old',1000,'预算100万',thread_id='omt_old')],'has_more':True,'page_token':'second'}
        return {'messages':[self.msg('om_new',3000,'预算60万')],'has_more':False,'page_token':None}
    def replies(self, thread_id, page_token=None): return {'messages':[self.msg('om_reply',2000,'确认')],'has_more':False,'page_token':None}
    def details(self, ids): return []
    def msg(self, mid, t, text, **extra): return {'message_id':mid,'create_time':str(t*1000),'content':text,'sender':{'id':'ou_test','name':'甲方'},'deleted':False,**extra}

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=App(Path(self.tmp.name)/'data');self.addCleanup(self.app.close)
        self.pid=self.app.execute('project.create',{'name':'项目'},request_id='create')['data']['project_id']
        self.reader=FakeReader();self.m=Monitor(self.app,self.reader)
        self.mon=self.call('add',{'chat_id':'oc_test'})['monitor_id']
    def call(self, action, payload=None): return self.m.execute(action,payload or {},self.pid)
    def begin(self):
        run=self.call('begin',{'monitor_id':self.mon,'force':True})
        return {'run_id':run['run_id'],'token':run['token']}
    def test_full_history_all_pages_before_chronological_queue(self):
        auth=self.begin()
        first=self.call('fetch',{**auth,'page_budget':1})
        self.assertFalse(first['fetch_complete'])
        with self.assertRaises(YuError):self.call('pending',auth)
        done=self.call('fetch',{**auth,'page_budget':10});self.assertTrue(done['fetch_complete'])
        pending=self.call('pending',auth)['messages']
        self.assertEqual([m['message_id'] for m in pending],['om_old','om_reply','om_new'])
        self.assertEqual(pending[1]['message']['thread_id'],'omt_old')
        self.assertIsNone(self.reader.calls[0][0])
        self.assertEqual(self.reader.calls[0][1],self.reader.calls[1][1])
    def test_pause_and_foreign_project_reject_run_writes(self):
        auth=self.begin();self.call('pause',{'monitor_id':self.mon,'version':1})
        with self.assertRaises(YuError):self.call('fetch',auth)
        other=self.app.execute('project.create',{'name':'其他'},request_id='other')['data']['project_id']
        with self.assertRaises(YuError):self.m.execute('fetch',auth,other)
    def test_same_chat_add_is_idempotent_and_default_interval(self):
        again=self.call('add',{'chat_id':'oc_test'})
        self.assertEqual(again['monitor_id'],self.mon)
        record=self.call('show',{'monitor_id':self.mon})
        self.assertEqual(record['interval_minutes'],60)
        self.assertFalse(record['history_complete'])
    def test_failure_keeps_window_and_incomplete_flag(self):
        auth=self.begin();self.reader.fail=True
        with self.assertRaises(YuError):self.call('fetch',auth)
        self.reader.fail=False
        self.assertTrue(self.call('fetch',{**auth,'page_budget':10})['fetch_complete'])
    def test_finish_requires_dispositions(self):
        auth=self.begin();self.call('fetch',{**auth,'page_budget':10})
        with self.assertRaises(YuError):self.call('finish',auth)
        pending=self.call('pending',auth)['messages']
        for msg in pending:self.call('resolve',{**auth,'message_versions':[msg['id']],'outcome':'no_change','reason':'无业务变化'})
        self.assertTrue(self.call('finish',auth)['completed'])
        again=self.begin();self.call('fetch',{**again,'page_budget':10})
        self.assertEqual(self.call('pending',again)['messages'],[])

    def fetched(self):
        auth=self.begin();self.call('fetch',{**auth,'page_budget':20})
        return auth,self.call('pending',auth)['messages']
    def step(self,auth,vid,key,command,payload):
        return self.call('step',{**auth,'message_versions':[vid],'step_key':key,'command':command,'input':payload})
    def draft(self,source,amount,base=None,supersedes=None):
        op={'op_id':'budget','type_key':'budget_range','scope_key':'project','base_revision':base['revision_id'] if base else None,
            'set_items':[{'item_id':'budget','data':{'currency':'CNY','max_minor':amount},'epistemic_kind':'adopted_decision',
                          'source_refs':[{'evidence_id':'message','source_version_id':source,'kind':'instruction'}],'dependencies':[]}]}
        if base:op['object_id']=base['object_id']
        decision={'decision_key':'budget','statement':'采用预算 '+amount,'decided_by':'客户','instruction_source_version_id':source,'rationale':'客户群内确认','affected_items':[{'op_id':'budget','item_id':'budget'}]}
        if supersedes:decision['supersedes_id']=supersedes
        return {'api_version':'1','command':'draft.apply','reason':'群内确认预算','objects':[op],'decisions':[decision]}
    def review(self,draft,text,base=None,cause=None):
        target={'type_key':'debrief','scope_key':'project'}
        if base:target['object_id']=base['object_id']
        return {'api_version':'1','command':'review.publish','reason':'同步预算段落','documents':[{'target':target,'base_revision':base['revision_id'] if base else None,
            'read_basis':[{'object_id':draft['object_id'],'revision_id':draft['revision_id']}],'structure_cause_change_ids':[],
            'set_blocks':[{'block_id':'budget','markdown':text,'dependencies':[{'dependency_id':'budget','object_id':draft['object_id'],'revision_id':draft['revision_id'],'item_id':'budget','kind':'fact'}],'cause_change_ids':[cause] if cause else []}]}]}
    def test_chronological_decisions_review_recovery_and_atomic_replay(self):
        auth,msgs=self.fetched();first=msgs[0]['id'];last=msgs[-1]['id']
        src=self.call('capture',{**auth,'message_version':first})['source_version_id']
        payload=self.draft(src,'100000000')
        result=self.step(auth,first,'budget_old','draft.apply',payload);draft=result['data']['objects'][0]
        replay=self.step(auth,first,'budget_old','draft.apply',payload)
        self.assertEqual(replay['meta']['change_id'],result['meta']['change_id'])
        initial=self.step(auth,first,'review_old','review.publish',self.review(draft,'预算 100 万'))['data']['documents'][0]
        self.call('resolve',{**auth,'message_versions':[first],'outcome':'applied','reason':'已采用','change_ids':[result['meta']['change_id']]})
        self.call('resolve',{**auth,'message_versions':[msgs[1]['id']],'outcome':'no_change','reason':'已记录的确认'})
        src=self.call('capture',{**auth,'message_version':last})['source_version_id']
        changed=self.step(auth,last,'budget_new','draft.apply',self.draft(src,'60000000',draft,result['data']['decisions'][0]['decision_id']))
        self.call('resolve',{**auth,'message_versions':[last],'outcome':'applied','reason':'预算变更','change_ids':[changed['meta']['change_id']]})
        with self.assertRaises(YuError) as error:self.call('finish',auth)
        self.assertEqual(error.exception.code,'MONITOR_REVIEW_PENDING')
        # Resume after draft commit and disposition: a resolved message still supports this run's review.
        obj=changed['data']['objects'][0]
        final=self.step(auth,last,'review_new','review.publish',self.review(obj,'预算 60 万',initial,changed['meta']['change_id']))
        self.assertEqual(final['data']['documents'][0]['version'],2)
        self.assertTrue(self.call('finish',auth)['completed'])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM decisions').fetchone()[0],2)
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM source_versions').fetchone()[0],2)

    def test_open_project_question_can_be_recorded_without_client_qa(self):
        self.reader.messages=lambda *args,**kwargs: {'messages':[self.reader.msg('om_question',1000,'如何让观众更愿意参与？')],'has_more':False,'page_token':None}
        auth,msgs=self.fetched();vid=msgs[0]['id']
        source=self.call('capture',{**auth,'message_version':vid})['source_version_id']
        payload={'api_version':'1','command':'draft.apply','reason':'保留开放讨论','decisions':[],
            'objects':[{'op_id':'discussion','type_key':'open_questions','scope_key':'project','base_revision':None,
              'set_items':[{'item_id':'participation','data':{'question':'如何让观众更愿意参与？','status':'open'},
                'epistemic_kind':'source_statement','source_refs':[{'evidence_id':'message','source_version_id':source,'kind':'supports'}],'dependencies':[]}]}]}
        result=self.step(auth,vid,'discussion','draft.apply',payload)
        again=self.step(auth,vid,'discussion','draft.apply',payload)
        self.assertEqual(again['meta']['change_id'],result['meta']['change_id'])
        self.call('resolve',{**auth,'message_versions':[vid],'outcome':'clarification','reason':'保留待讨论议题','change_ids':[result['meta']['change_id']]})
        self.assertTrue(self.call('finish',auth)['completed'])
        self.assertEqual(self.app.db.execute("SELECT count(*) FROM objects WHERE type_key='qa'").fetchone()[0],0)
        self.assertEqual(self.app.db.execute("SELECT count(*) FROM objects WHERE type_key='open_questions'").fetchone()[0],1)

    def test_step_commit_and_receipt_roll_back_together(self):
        auth,msgs=self.fetched();vid=msgs[0]['id']
        source=self.call('capture',{**auth,'message_version':vid})['source_version_id']
        self.app.db.execute("CREATE TRIGGER break_receipt BEFORE UPDATE OF result_json ON monitor_steps WHEN NEW.command='draft.apply' BEGIN SELECT RAISE(ABORT,'injected'); END;")
        with self.assertRaises(sqlite3.IntegrityError):self.step(auth,vid,'atomic','draft.apply',self.draft(source,'100'))
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM decisions').fetchone()[0],0)
        self.app.db.execute('DROP TRIGGER break_receipt')
        result=self.step(auth,vid,'atomic','draft.apply',self.draft(source,'100'))
        self.assertIsNotNone(result['meta']['change_id'])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM decisions').fetchone()[0],1)

    def test_expired_lease_fences_old_worker_and_resumes_same_run(self):
        auth=self.begin();self.call('fetch',{**auth,'page_budget':1})
        self.app.db.execute("UPDATE monitor_leases SET expires_at='2000-01-01T00:00:00Z'")
        replacement=self.begin();self.assertEqual(auth['run_id'],replacement['run_id']);self.assertNotEqual(auth['token'],replacement['token'])
        with self.assertRaises(YuError):self.call('fetch',auth)
        self.call('fetch',{**replacement,'restart_window':True,'page_budget':20})
        self.assertEqual(len(self.call('pending',replacement)['messages']),3)

    def test_failed_step_can_be_abandoned_but_committed_step_cannot(self):
        auth,msgs=self.fetched();vid=msgs[0]['id']
        with self.assertRaises(YuError):self.step(auth,vid,'invalid','draft.apply',{})
        self.call('discard-step',{**auth,'step_key':'invalid','reason':'修正错误输入，使用新步骤身份'})
        self.assertEqual(self.call('pending',auth)['unfinished_steps'],[])
        captured=self.call('capture',{**auth,'message_version':vid})
        with self.assertRaises(YuError):self.call('discard-step',{**auth,'step_key':'capture_'+vid,'reason':'不能撤销已保存证据'})

    def test_scheduler_is_unbound_until_receipt_and_restore_pauses(self):
        schedule=self.call('schedule',{'monitor_id':self.mon})
        self.assertTrue(schedule['requires_host_automation_tool']);self.assertEqual(schedule['schedule'],{})
        self.call('scheduler-bind',{'monitor_id':self.mon,'version':1,'schedule':{'automation_id':'fixture','thread_id':'fixture','host_id':'fixture','state':'active','interval_minutes':60}})
        self.begin();backup=Path(self.tmp.name)/'backup';restored=Path(self.tmp.name)/'restored'
        create_backup(self.app.data_dir,backup);verify_backup(backup);restore_backup(backup,restored)
        other=App(restored)
        try:
            row=other.db.execute('SELECT status,schedule_json FROM chat_monitors').fetchone()
            self.assertEqual(tuple(row),('paused','{}'));self.assertEqual(other.db.execute('SELECT count(*) FROM monitor_leases').fetchone()[0],0)
        finally:other.close()

    def test_edit_reversion_has_distinct_versions_and_out_of_order_draft_rejected(self):
        auth,msgs=self.fetched()
        with self.assertRaises(YuError):self.step(auth,msgs[-1]['id'],'out_of_order','draft.apply',{})
        row=self.m.monitor(self.pid,self.mon);cursor={'threads':[]}
        for text in ['改为80万','预算100万']:
            with self.m.transaction():self.m._store(row,self.reader.msg('om_old',1000,text,thread_id='omt_old'),now(),cursor)
        self.assertEqual(self.app.db.execute("SELECT count(*) FROM monitor_messages WHERE message_id='om_old'").fetchone()[0],3)

    def test_same_content_advances_remote_edit_watermark(self):
        row=self.m.monitor(self.pid,self.mon);cursor={'threads':[]}
        for text,updated in [('A',100),('A',300),('B',200)]:
            with self.m.transaction():self.m._store(row,self.reader.msg('om_watermark',10,text,update_time=str(updated*1000)),now(),cursor)
        messages=list(self.app.db.execute("SELECT * FROM monitor_messages WHERE message_id='om_watermark'"))
        self.assertEqual(len(messages),1);self.assertEqual(json.loads(messages[0]['payload_json'])['content'],'A')
        self.assertEqual(messages[0]['remote_updated_at'],'1970-01-01T00:05:00.000000Z')

    def test_daily_recheck_ignores_irrelevant_old_messages(self):
        auth,msgs=self.fetched()
        for msg in msgs:self.call('resolve',{**auth,'message_versions':[msg['id']],'outcome':'no_change','reason':'无业务信息'})
        self.call('finish',auth)
        self.app.db.execute("UPDATE chat_monitors SET last_recheck_at='2000-01-01T00:00:00.000000Z'")
        again=self.begin()
        cursor=json.loads(self.app.db.execute('SELECT cursor_json FROM monitor_runs WHERE id=?',(again['run_id'],)).fetchone()[0])
        self.assertEqual(cursor['recheck_ids'],[])

    def test_daily_recheck_retains_current_object_evidence(self):
        auth,msgs=self.fetched();first=msgs[0]['id']
        source=self.call('capture',{**auth,'message_version':first})['source_version_id']
        saved=self.step(auth,first,'retain_evidence','draft.apply',self.draft(source,'100'))
        self.call('resolve',{**auth,'message_versions':[first],'outcome':'applied','reason':'已保存','change_ids':[saved['meta']['change_id']]})
        for msg in msgs[1:]:self.call('resolve',{**auth,'message_versions':[msg['id']],'outcome':'no_change','reason':'无变化'})
        self.call('finish',auth)
        self.app.db.execute("UPDATE chat_monitors SET last_recheck_at='2000-01-01T00:00:00.000000Z'")
        again=self.begin()
        cursor=json.loads(self.app.db.execute('SELECT cursor_json FROM monitor_runs WHERE id=?',(again['run_id'],)).fetchone()[0])
        self.assertEqual(cursor['recheck_ids'],['om_old'])

    def test_nested_and_separate_reply_pages_share_context_without_false_edit(self):
        row=self.m.monitor(self.pid,self.mon);cursor={'threads':[]}
        root=self.reader.msg('om_root',10,'问题',thread_id='omt_topic',thread_replies=[self.reader.msg('om_child',20,'确认',parent_id='om_root')])
        with self.m.transaction():
            self.m._store(row,root,now(),cursor)
            self.m._store(row,self.reader.msg('om_child',20,'确认',thread_id='omt_topic'),now(),cursor)
        rows=list(self.app.db.execute("SELECT * FROM monitor_messages WHERE message_id='om_child'"))
        self.assertEqual(len(rows),1)
        msg=json.loads(rows[0]['payload_json']);self.assertEqual(msg['thread_id'],'omt_topic');self.assertEqual(msg['parent_id'],'om_root')
        host=self.reader.msg('om_reply_host',25,'另一条回复',thread_id='omt_topic',thread_replies=[self.reader.msg('om_sibling',30,'收到')])
        with self.m.transaction():self.m._store(row,host,now(),cursor)
        msg=json.loads(self.app.db.execute("SELECT payload_json FROM monitor_messages WHERE message_id='om_sibling'").fetchone()[0])
        self.assertEqual(msg['thread_id'],'omt_topic');self.assertNotIn('parent_id',msg);self.assertNotIn('root_id',msg)

    def test_unknown_fields_and_non_boolean_flags_are_rejected(self):
        for action,payload in [('add',{'chat_id':'oc_test','interval_minuts':15}),('begin',{'monitor_id':self.mon,'force':'false'}),('pause',{'monitor_id':self.mon,'version':True})]:
            with self.subTest(action=action):
                with self.assertRaises(YuError) as error:self.call(action,payload)
                self.assertEqual(error.exception.code,'INVALID_INPUT')

    def test_clock_rollback_does_not_create_an_impossible_window(self):
        auth,msgs=self.fetched()
        for msg in msgs:self.call('resolve',{**auth,'message_versions':[msg['id']],'outcome':'no_change','reason':'无变化'})
        self.call('finish',auth)
        with patch('yuplus.monitor.now',return_value=shifted(now(),-3600)):
            with self.assertRaises(YuError) as error:self.begin()
        self.assertEqual(error.exception.code,'MONITOR_CLOCK_SKEW')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM monitor_runs').fetchone()[0],1)
        self.assertTrue(self.begin()['run_id'])

    def test_schema_one_is_backed_up_before_additive_migration(self):
        old=Path(self.tmp.name)/'legacy';old.mkdir()
        db=sqlite3.connect(old/'yuplus.sqlite');db.executescript((Path(__file__).parents[1]/'src/yuplus/contracts/schema.sql').read_text());db.close()
        migrated=App(old)
        try:self.assertEqual(migrated.db.execute('PRAGMA user_version').fetchone()[0],11)
        finally:migrated.close()
        backups=list((Path(self.tmp.name)/'legacy-migration-backups').iterdir());self.assertEqual(len(backups),1)
        verify_backup(backups[0]);db=sqlite3.connect(backups[0]/'yuplus.sqlite')
        try:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
        finally:db.close()

    def test_project_delete_pauses_monitor_invalidates_lease_and_returns_host_receipt(self):
        auth=self.begin()
        schedule={'automation_id':'task_fixture','thread_id':'thread_fixture','host_id':'local','state':'active','interval_minutes':60}
        self.call('scheduler-bind',{'monitor_id':self.mon,'version':1,'schedule':schedule})
        result=self.app.execute('project.delete',{'base_metadata_version':1},project_id=self.pid,request_id='delete_monitor_project')['data']
        self.assertEqual(result['scheduler_actions'][0]['schedule']['automation_id'],'task_fixture')
        self.assertEqual(self.call('show',{'monitor_id':self.mon})['status'],'paused')
        with self.assertRaises(YuError):self.call('fetch',{**auth,'page_budget':10})
        with self.assertRaises(YuError):self.begin()
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM monitor_leases').fetchone()[0],0)
