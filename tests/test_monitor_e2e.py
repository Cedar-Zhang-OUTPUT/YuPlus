"""Real CLI subprocesses and HTTP; only the external Feishu provider is a fixture."""
import http.client
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from yuplus.gateway import GatewayServer
from tests import test_monitor as helpers


FAKE_LARK = '''#!/usr/bin/env python3
import json,os,sys
from datetime import datetime
args=sys.argv[1:]
state=json.load(open(os.environ['YUPLUS_TEST_FEISHU_STATE']))
def val(flag,default=None):return args[args.index(flag)+1] if flag in args else default
if args[:2]==['auth','status']:
 print(json.dumps({'identity':'user','identities':{'user':{'openId':'ou_test'}}}));sys.exit()
assert val('--as')=='user' and val('--format')=='json'
if args[:3]==['im','chats','get']:data={'chat_id':'oc_test','tenant_key':'tenant','name':'城市展项目群'}
elif args[:2]==['im','+chat-messages-list']:
 rows=state['roots']; start=val('--start'); end=val('--end')
 def stamp(x):return int(x) if str(x).isdigit() else datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()*1000
 rows=[r for r in rows if (not start or stamp(r.get('filter_time',r['create_time']))>=stamp(start)) and (not end or stamp(r.get('filter_time',r['create_time']))<=stamp(end))]
 index=int(val('--page-token','0'));page=rows[index:index+1];more=index+1<len(rows)
 data={'messages':page,'total':len(page),'has_more':more,'page_token':str(index+1) if more else None}
elif args[:2]==['im','+threads-messages-list']:
 rows=state['replies'];data={'messages':rows,'total':len(rows),'has_more':False,'page_token':None}
elif args[:2]==['im','+messages-mget']:
 ids=val('--message-ids').split(',');rows=[r for r in state['roots']+state['replies'] if r['message_id'] in ids]
 data={'messages':rows,'total':len(rows)}
else:raise Exception('Unsupported fixture call: '+str(args))
print(json.dumps({'ok':True,'identity':'user','data':data}))
'''


class MonitorE2ETests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'data'
        binary=self.root/'bin';binary.mkdir();lark=binary/'lark-cli';lark.write_text(FAKE_LARK);lark.chmod(0o755)
        self.state=self.root/'provider.json';reader=helpers.FakeReader()
        self.state.write_text(json.dumps({'roots':[reader.msg('om_old',1000,'采用预算100万',thread_id='omt_old'),reader.msg('om_new',3000,'改为预算60万')],'replies':[reader.msg('om_reply',2000,'收到确认')]}))
        self.env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1]/'src'),'PATH':str(binary)+os.pathsep+str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH',''),'YUPLUS_TEST_FEISHU_STATE':str(self.state)}
        self.serial=0
        self.pid=self.cli(['project','create','--name','城市展项目群监控验证','--request-id','create'])['data']['project_id']
    def cli(self,args,payload=None,ok=True,data=None):
        command=[sys.executable,'-m','yuplus','--data-dir',str(data or self.data),*args]
        if payload is not None:command+=['--input','-']
        result=subprocess.run(command,input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True,env=self.env,timeout=20)
        self.assertEqual(result.returncode==0,ok,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['ok'],ok);return value
    def monitor(self,action,payload=None,ok=True):return self.cli(['monitor',action,'--project',self.pid],payload,ok)
    def step(self,auth,vid,key,command,payload):return self.monitor('step',{**auth,'message_versions':[vid],'step_key':key,'command':command,'input':payload})['data']
    def test_full_cli_service_chain_retry_and_restore(self):
        self.mid=self.monitor('add',{'chat_id':'oc_test'})['data']['monitor_id']
        # This fixture does not create an automation: scheduler receipt remains unbound.
        schedule=self.monitor('schedule',{'monitor_id':self.mid})['data'];self.assertEqual(schedule['schedule'],{})
        run=self.monitor('begin',{'monitor_id':self.mid})['data'];auth={k:run[k] for k in ('run_id','token')}
        self.assertFalse(self.monitor('fetch',{**auth,'page_budget':1})['data']['fetch_complete'])
        self.monitor('pending',auth,ok=False)
        self.assertTrue(self.monitor('fetch',{**auth,'page_budget':20})['data']['fetch_complete'])
        msgs=self.monitor('pending',auth)['data']['messages'];self.assertEqual([m['message_id'] for m in msgs],['om_old','om_reply','om_new'])
        draft=None;review=None;decision=None
        for index,msg in enumerate(msgs):
            vid=msg['id']
            if index==1:
                self.monitor('resolve',{**auth,'message_versions':[vid],'outcome':'no_change','reason':'重复确认不新增决定'});continue
            source=self.monitor('capture',{**auth,'message_version':vid})['data']['source_version_id']
            request=helpers.MonitorTests.draft(self,source,'100000000' if index==0 else '60000000',draft,decision)
            result=self.step(auth,vid,'draft_'+str(index),'draft.apply',request);draft=result['data']['objects'][0];decision=result['data']['decisions'][0]['decision_id']
            self.assertEqual(result,self.step(auth,vid,'draft_'+str(index),'draft.apply',request))
            self.monitor('resolve',{**auth,'message_versions':[vid],'outcome':'applied','reason':'按客户原话维护预算','change_ids':[result['meta']['change_id']]})
            if index==2:
                self.assertEqual(self.monitor('finish',auth,ok=False)['error']['code'],'MONITOR_REVIEW_PENDING')
            request=helpers.MonitorTests.review(self,draft,'预算100万' if index==0 else '预算60万',review,result['meta']['change_id'] if review else None)
            review=self.step(auth,vid,'review_'+str(index),'review.publish',request)['data']['documents'][0]
        self.monitor('finish',{**auth,'summary':'按时间顺序记录预算100万→60万，已同步主策成果。'})
        # New process / new check: identical fetched messages never duplicate adopted decisions.
        second=self.monitor('begin',{'monitor_id':self.mid,'force':True})['data'];auth2={k:second[k] for k in ('run_id','token')}
        self.monitor('fetch',{**auth2,'page_budget':20});self.assertEqual(self.monitor('pending',auth2)['data']['messages'],[])
        self.monitor('finish',{**auth2,'summary':'无新增信息。'})
        decisions=self.cli(['decisions','list','--project',self.pid])['data']['decisions'];self.assertEqual(len(decisions),2)
        backup=self.root/'backup';restored=self.root/'restored'
        self.cli(['backup','create','--output',str(backup)]);self.cli(['backup','restore','--input',str(backup)],data=restored)
        self.assertEqual(self.cli(['monitor','list','--project',self.pid],data=restored)['data']['monitors'][0]['status'],'paused')
        self.server=GatewayServer(self.data,0);thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def stop():self.server.shutdown();self.server.server_close();thread.join()
        self.addCleanup(stop)
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        conn.request('GET','/api/view?project='+self.pid);response=conn.getresponse();raw=response.read();conn.close()
        self.assertEqual(response.status,200);view=json.loads(raw)
        monitor=view['chat_monitors'][0];self.assertEqual(monitor['chat_name'],'城市展项目群');self.assertTrue(monitor['history_complete'])
        self.assertEqual(monitor['pending_count'],0);self.assertNotIn(run['token'],raw.decode());self.assertNotIn('payload_json',raw.decode())
        self.assertEqual(len(view['monitor_runs']),2)
        self.assertTrue(any('60万' in json.dumps(r,ensure_ascii=False) for r in view['object_revisions']))

    def use_local_time_fixture(self):
        self.env['TZ']='Asia/Shanghai'
        state=json.loads(self.state.read_text())
        state['roots'][0]['create_time']='2025-12-11 14:52'
        state['replies'][0]['create_time']='2025-12-11 14:53:01'
        state['roots'][1].update(create_time='2025-12-11 14:54',update_time='2025-12-11 15:02')
        self.state.write_text(json.dumps(state))
        return state

    def test_local_time_full_cli_draft_review_chain(self):
        self.use_local_time_fixture()
        self.test_full_cli_service_chain_retry_and_restore()
        with sqlite3.connect(self.data/'yuplus.sqlite') as db:
            stored=db.execute("SELECT created_at,remote_updated_at,payload_json FROM monitor_messages WHERE message_id='om_new'").fetchall()
        self.assertEqual(len(stored),1)
        self.assertEqual(stored[0][:2],('2025-12-11T06:54:00.000000Z','2025-12-11T07:02:00.000000Z'))
        self.assertEqual(json.loads(stored[0][2])['create_time'],'2025-12-11 14:54')

    def test_interrupted_history_retries_checkpoint_without_duplicate_messages(self):
        state=self.use_local_time_fixture()
        state['roots'][1].update(filter_time='2025-12-11 14:54',create_time='bad')
        self.state.write_text(json.dumps(state))
        mid=self.monitor('add',{'chat_id':'oc_test'})['data']['monitor_id']
        run=self.monitor('begin',{'monitor_id':mid})['data'];auth={k:run[k] for k in ('run_id','token')}
        self.monitor('fetch',{**auth,'page_budget':1})
        error=self.monitor('fetch',{**auth,'page_budget':20},ok=False)
        self.assertEqual(error['error']['code'],'FEISHU_UNAVAILABLE')
        with sqlite3.connect(self.data/'yuplus.sqlite') as db:
            checkpoint=db.execute('SELECT cursor_json,fetch_complete FROM monitor_runs WHERE id=?',(run['run_id'],)).fetchone()
            self.assertEqual(json.loads(checkpoint[0])['page_token'],'1')
            self.assertEqual(checkpoint[1],0)
            self.assertEqual(db.execute('SELECT count(*) FROM monitor_messages').fetchone()[0],1)
        state['roots'][1]['create_time']='2025-12-11 14:54'
        self.state.write_text(json.dumps(state))
        self.assertTrue(self.monitor('fetch',{**auth,'page_budget':20})['data']['fetch_complete'])
        pending=self.monitor('pending',auth)['data']['messages']
        self.assertEqual([m['message_id'] for m in pending],['om_old','om_reply','om_new'])
        self.assertEqual(self.monitor('pending',auth)['data']['messages'],pending)
        for msg in pending:
            self.monitor('resolve',{**auth,'message_versions':[msg['id']],'outcome':'no_change','reason':'模拟消息无业务改动'})
        self.monitor('finish',{**auth,'summary':'完成断点续读验证'})
        with sqlite3.connect(self.data/'yuplus.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM monitor_messages').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT history_complete,last_error FROM chat_monitors WHERE id=?',(mid,)).fetchone(),(1,None))

    def test_group_discussion_and_attachment_become_two_readable_sources(self):
        reader=helpers.FakeReader()
        self.state.write_text(json.dumps({'roots':[
            reader.msg('om_file',1000,'<file key="file_fixture" name="项目 Brief.txt"/>'),
            reader.msg('om_question',2000,'快闪日也有晚宴？'),
            reader.msg('om_answer',3000,'是的')], 'replies':[]}))
        mid=self.monitor('add',{'chat_id':'oc_test'})['data']['monitor_id']
        run=self.monitor('begin',{'monitor_id':mid})['data'];auth={k:run[k] for k in ('run_id','token')}
        self.monitor('fetch',{**auth,'page_budget':20})
        messages=self.monitor('pending',auth)['data']['messages'];ids=[m['id'] for m in messages]
        segment=self.monitor('capture',{**auth,'message_versions':ids[1:],'title':'活动形式 · 快闪日晚宴确认'})['data']
        attachment=self.root/'项目 Brief.txt';attachment.write_text('项目希望通过快闪活动开展品牌展示。')
        imported=self.step(auth,ids[0],'attachment','source.import',{
            'api_version':'1','command':'source.import','target':{'mode':'create','provider':'local','resource_type':'file','provider_key':'feishu-file-fixture'},
            'snapshot':{'title':'项目 Brief.txt','provider_revision':None,'captured_at':'2026-10-22T00:00:00Z',
                        'capture_scope':{'kind':'whole_resource'},'extraction_profile':'text-verbatim-v1',
                        'body':{'format':'text','text':attachment.read_text()},'provenance':{'method':'downloaded-chat-attachment'},
                        'assets':[{'asset_id':'brief_file','role':'original','display_name':attachment.name,'mime_type':'text/plain',
                                   'local_path':str(attachment),'storage':'copy',
                                   'locator':{'message_id':'om_file','message_url':'https://applink.feishu.cn/client/chat/open?openChatId=oc_test'}}]},
            'advance_head':True,'reason':'保存实际文件内容与聊天出处'})['data']
        draft=self.monitor('step',{**auth,'message_versions':ids,'step_key':'brief_facts','command':'draft.apply','input':{
            'api_version':'1','command':'draft.apply','reason':'依据文件及完整问答维护项目事实','objects':[{
                'op_id':'brief','type_key':'client_brief','scope_key':'project','base_revision':None,
                'set_items':[{'item_id':'activity','data':{'requirement':'快闪活动开展品牌展示，快闪日包含晚宴。'},
                              'epistemic_kind':'source_statement','source_refs':[
                                  {'evidence_id':'brief','source_version_id':imported['snapshot_id'],'asset_id':'brief_file','kind':'supports'},
                                  {'evidence_id':'discussion','source_version_id':segment['source_version_id'],'kind':'supports'}],
                              'dependencies':[]}]}],'decisions':[]}})
        self.monitor('resolve',{**auth,'message_versions':ids,'outcome':'applied','reason':'已读取文件并结合问答更新业务事实','change_ids':[draft['data']['meta']['change_id']]})
        self.monitor('finish',{**auth,'summary':'一份文件、一段讨论，维护一条业务事实'})
        sources=self.cli(['source','list','--project',self.pid])['data']['sources']
        self.assertEqual(len(sources),2)
        self.assertEqual({s['cached_title'] for s in sources},{'项目 Brief.txt','活动形式 · 快闪日晚宴确认'})
        with sqlite3.connect(self.data/'yuplus.sqlite') as db:
            self.assertEqual(db.execute("SELECT count(*) FROM sources WHERE resource_type='message'").fetchone()[0],0)
        saved=self.cli(['draft','show','--project',self.pid,'--object',draft['data']['data']['objects'][0]['object_id']])['data']
        self.assertNotIn('file_fixture',json.dumps(saved['items']))
        self.assertEqual(len(saved['items']),1)
        attachment.unlink()
        source=self.cli(['source','show','--project',self.pid,'--source',imported['source_id'],'--include-body'])['data']
        self.assertEqual(source['snapshot']['body']['text'],'项目希望通过快闪活动开展品牌展示。')
