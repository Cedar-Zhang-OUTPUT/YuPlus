"""Real CLI subprocesses and HTTP; only the external Feishu provider is a fixture."""
import http.client
import json
import os
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
 def stamp(x):return datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()*1000
 rows=[r for r in rows if (not start or int(r['create_time'])>=stamp(start)) and (not end or int(r['create_time'])<=stamp(end))]
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
