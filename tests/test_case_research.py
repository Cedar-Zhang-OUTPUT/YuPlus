import concurrent.futures
import http.client
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from yuplus.app import App
from yuplus.backup import create_backup, restore_backup
from yuplus.case_preview import PreviewCache
from yuplus.core import YuError
from yuplus.gateway import GatewayServer
from test_appearance import png


class ResearchTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.data=self.root/'data';self.app=App(self.data);self.addCleanup(self.app.close)
        self.pid=self.app.execute('project.create',{'name':'研究验证'},request_id='create_p')['data']['project_id']
        self.other=self.app.execute('project.create',{'name':'其他'},request_id='create_q')['data']['project_id']

    def write(self,action,request,**kwargs):
        return self.app.execute('research.'+action,{'api_version':'1','command':'research.'+action,**kwargs},project_id=self.pid,request_id=request)

    def round(self,request='round1',token='board1'):
        row=self.write('create',request,title='案例研究')['data']
        return self.write('update',request+'_bind',research_id=row['id'],base_version=1,document_url='https://team.feishu.cn/docx/Doc1',board_url='https://team.feishu.cn/docx/Doc1#block1',board_token=token)['data']

    def test_rounds_replay_updates_scope_and_independence(self):
        a=self.round(); b=self.round('round2','board2')
        self.assertEqual((a['version'],b['version']),(1,2))
        self.assertTrue(self.write('create','round1',title='案例研究')['meta']['replayed'])
        updated=self.write('update','edited',research_id=a['id'],base_version=2)['data']
        self.assertEqual(updated['version'],1);self.assertEqual(updated['metadata_version'],3)
        with self.assertRaises(YuError) as cm:self.write('update','stale',research_id=a['id'],base_version=2)
        self.assertEqual(cm.exception.code,'VERSION_CONFLICT')
        with self.assertRaises(YuError):self.app.execute('research.show',{'research_id':a['id']},project_id=self.other)
        with self.assertRaises(YuError):self.write('create','round1',title='different')
        with self.assertRaises(YuError):self.round('round3','board1')
        with self.assertRaises(YuError):self.write('update','swap',research_id=a['id'],base_version=3,document_url=a['document_url'],board_url=a['board_url'],board_token='different')
        for table in ('objects','sources','decisions'):self.assertEqual(self.app.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
        self.assertEqual(self.app.cursor(self.pid),1)
        self.assertEqual(len(self.app.execute('research.list',project_id=self.pid)['data']['research']),3)

    def test_validation_and_archived_project(self):
        r=self.write('create','new',title='新研究')['data']
        with self.assertRaises(YuError):self.write('create','body',title='研究',content='不存正文')
        for doc,board,token in [('http://team.feishu.cn/docx/A','https://team.feishu.cn/docx/A#b','w'),('https://team.feishu.cn/docx/A','https://evil.test/docx/A#b','w'),('https://team.feishu.cn/docx/A','https://team.feishu.cn/docx/B#b','w'),('https://team.feishu.cn/docx/A','https://team.feishu.cn/docx/A','w'),('https://team.feishu.cn/docx/A','https://team.feishu.cn/docx/A#b','--overwrite')]:
            with self.assertRaises(YuError):self.write('update','invalid',research_id=r['id'],base_version=1,document_url=doc,board_url=board,board_token=token)
        self.app.execute('project.delete',{'base_metadata_version':1},project_id=self.pid,request_id='delete')
        with self.assertRaises(YuError):self.app.execute('research.preview',{'research_id':r['id']},project_id=self.pid)
        self.assertEqual(self.app.execute('research.show',{'research_id':r['id']},project_id=self.pid)['data']['id'],r['id'])

    def test_migration_backup_and_restore(self):
        self.app.db.execute('DROP TABLE case_research_requests');self.app.db.execute('DROP TABLE case_research');self.app.db.execute('PRAGMA user_version=6')
        migrated=App(self.data);migrated.close()
        self.assertEqual(self.app.execute('doctor')['data']['schema_version'],11)
        backups=list((self.root/'data-migration-backups').iterdir());self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]/'yuplus.sqlite') as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],6)
        r=self.round();backup=self.root/'backup';create_backup(self.data,backup);restore_backup(backup,self.root/'restored')
        restored=App(self.root/'restored')
        try:self.assertEqual(restored.execute('research.show',{'research_id':r['id']},project_id=self.pid)['data'],r)
        finally:restored.close()
        self.assertFalse(any('preview' in str(p.relative_to(backup)) for p in backup.rglob('*')))

    def test_cache_coalesces_keeps_good_image_and_gateway_guards(self):
        row=self.round();calls=[];bad=False;auth=False
        def runner(argv,**kwargs):
            calls.append(argv);time.sleep(.05)
            if auth:raise YuError('FEISHU_UNAVAILABLE','auth',details=[{'type':'authorization','subtype':'missing_scope'}])
            Path(kwargs['cwd'],'preview.png').write_bytes(b'html' if bad else png())
            return {}
        cache=PreviewCache(self.data,root=self.root/'cache',runner=runner)
        with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(lambda _:cache.refresh(row),range(4)))
        self.assertEqual(len(calls),1);self.assertEqual(results[0],results[-1]);good=results[0]
        manifest=cache.root/(cache.prefix(row)+'.json')
        import os
        os.utime(manifest,(1,1));bad=True
        with self.assertRaises(YuError):cache.refresh(row)
        self.assertEqual(cache.cached(row),good)
        bad=False;auth=True
        with self.assertRaises(YuError) as cm:cache.refresh(row)
        self.assertEqual(cm.exception.code,'FORBIDDEN');self.assertEqual(cache.cached(row),good)
        auth=False
        server=GatewayServer(self.data,0);server.case_previews=cache
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def get(path,method='GET',headers=None):
            con=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);con.request(method,path,headers=headers or {})
            res=con.getresponse();raw=res.read();status=res.status;con.close();return status,raw
        try:
            url=f'/api/case-finding/preview?project={self.pid}&version={row["id"]}'
            self.assertEqual(get(url)[0],200)
            view=json.loads(get('/api/view?project='+self.pid)[1]);self.assertTrue(view['meta']['case_finding_preview']);self.assertIsNotNone(view['case_findings'][0]['preview'])
            self.assertEqual(get(good['image_url'])[1],png())
            self.assertEqual(get(url,'POST')[0],405)
            self.assertEqual(get(url,headers={'Origin':'https://evil.test'})[0],403)
            self.assertEqual(get(url.replace(self.pid,self.other))[0],404)
            self.app.execute('project.delete',{'base_metadata_version':1},project_id=self.pid,request_id='delete')
            self.assertEqual(get(good['image_url'])[0],404)
        finally:server.shutdown();server.server_close();thread.join()

    def test_cli_flow(self):
        payload=self.root/'create.json';payload.write_text(json.dumps({'api_version':'1','command':'research.create','title':'CLI研究'}))
        def cli(*args):
            p=subprocess.run([sys.executable,'-m','yuplus',*args,'--data-dir',str(self.data),'--project',self.pid],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);return json.loads(p.stdout)
        result=cli('research','create','--request-id','cli_create','--input',str(payload))['data']
        self.assertEqual(cli('research','show','--research',result['id'])['data'],result)
        self.assertEqual(cli('research','list')['data']['research'][0],result)
