import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from yuplus.app import App
from yuplus.core import YuError
from yuplus.browser_view import browser_view, read_snapshot
from yuplus.backup import create_backup, restore_backup

URL='https://example.feishu.cn/drive/folder/FolderOne'

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'data'
        self.app=App(self.data);self.addCleanup(self.app.close);self.n=0
    def write(self,action,**fields):
        self.n+=1
        return self.app.execute('library.'+action,{'api_version':'1','command':'library.'+action,**fields},request_id=f'req_{self.n}')['data']
    def test_lifecycle_replay_version_guard_and_global_view(self):
        payload={'api_version':'1','command':'library.add','name':'案例一','url':URL+'?from=share'}
        first=self.app.execute('library.add',payload,request_id='same')
        again=self.app.execute('library.add',payload,request_id='same')
        self.assertEqual(first['data'],again['data']);self.assertTrue(again['meta']['replayed'])
        self.assertEqual(first['meta']['library_policy']['storage'],'source_metadata_only')
        self.assertEqual(again['meta']['library_policy']['deletion'],'local_registration_only')
        row=first['data'];self.assertEqual(row['url'],URL)
        with self.assertRaises(YuError):self.app.execute('library.add',{**payload,'name':'different'},request_id='same')
        with self.assertRaises(YuError):self.write('add',name='重复',url=URL+'/')
        renamed=self.write('update',library_id=row['id'],base_version=1,name='新名称',url=URL)
        self.assertEqual(renamed['version'],2)
        with self.assertRaises(YuError):self.write('delete',library_id=row['id'],base_version=1)
        project=self.app.execute('project.create',{'name':'独立项目'},request_id='project')['data']['project_id']
        for pid in (None,project):
            with read_snapshot(self.data) as db:self.assertEqual(browser_view(db,self.data,pid)['case_libraries'][0]['name'],'新名称')
        self.write('delete',library_id=row['id'],base_version=2)
        self.assertEqual(self.app.execute('library.list')['data']['libraries'],[])
        self.assertEqual(len(self.app.execute('library.list',{'include_deleted':True})['data']['libraries']),1)
        self.write('restore',library_id=row['id'],base_version=3)
        with read_snapshot(self.data) as db:self.assertEqual(len(browser_view(db,self.data)['case_libraries']),1)
        backup=self.root/'backup';create_backup(self.data,backup);restored=self.root/'restored';restore_backup(backup,restored)
        with read_snapshot(restored) as db:self.assertEqual(browser_view(db,restored)['case_libraries'][0]['id'],row['id'])
    def test_invalid_inputs_and_project_scope_are_rejected(self):
        urls=['', 'javascript:alert(1)', 'https://evil.com/drive/folder/a','https://feishu.cn.evil.com/drive/folder/a',
              'https://foo.feishu.cn/docx/abc','https://user@foo.feishu.cn/drive/folder/a','https://foo.feishu.cn:99/drive/folder/a',URL+'\\x',None]
        for url in urls:
            with self.subTest(url=url),self.assertRaises(YuError):self.write('add',name='A',url=url)
        with self.assertRaises(YuError):self.app.execute('library.list',{},project_id='project')
        self.assertEqual(self.app.execute('library.list')['data']['libraries'],[])
    def test_schema_three_upgrade_preserves_projects_and_backs_up(self):
        legacy=self.root/'legacy';old=App(legacy)
        project=old.execute('project.create',{'name':'旧项目'},request_id='old')['data']['project_id']
        old.db.execute('DROP TABLE case_library_requests');old.db.execute('DROP TABLE case_libraries');old.db.execute('PRAGMA user_version=3');old.close()
        migrated=App(legacy)
        try:
            self.assertEqual(migrated.execute('doctor')['data']['schema_version'],5)
            self.assertEqual(migrated.execute('project.show',project_id=project)['data']['name'],'旧项目')
            self.assertEqual(migrated.execute('library.list')['data']['libraries'],[])
        finally:migrated.close()
        backups=list((self.root/'legacy-migration-backups').iterdir());self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]/'yuplus.sqlite') as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],3)
    def test_public_cli(self):
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
        def run(*args,payload=None):
            result=subprocess.run([sys.executable,'-m','yuplus','--data-dir',str(self.data),*args,'--json'],input=json.dumps(payload) if payload else None,text=True,capture_output=True,env=env)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr);return json.loads(result.stdout)['data']
        added=run('library','add','--request-id','cli_add','--input','-',payload={'api_version':'1','command':'library.add','name':'CLI案例库','url':URL})
        self.assertEqual(run('library','show','--library',added['id'])['name'],'CLI案例库')
        self.assertEqual(run('library','list')['libraries'][0]['id'],added['id'])
        deleted=run('library','delete','--request-id','cli_delete','--input','-',payload={'api_version':'1','command':'library.delete','library_id':added['id'],'base_version':added['version']})
        self.assertTrue(deleted['deleted_at'])
        self.assertEqual(run('library','list')['libraries'],[])
        self.assertEqual(run('library','list','--include-deleted')['libraries'][0]['id'],added['id'])
        restored=run('library','restore','--request-id','cli_restore','--input','-',payload={'api_version':'1','command':'library.restore','library_id':added['id'],'base_version':deleted['version']})
        self.assertIsNone(restored['deleted_at'])
        self.assertEqual(restored['url'],URL)
        self.assertEqual(run('library','list')['libraries'][0]['id'],added['id'])
        site=run('library','add','--request-id','cli_site','--input','-',payload={'api_version':'1','command':'library.add','kind':'website','name':'网站','url':'https://example.com/cases'})
        self.assertEqual(run('library','show','--library',site['id'])['kind'],'website')
        gone=run('library','delete','--request-id','cli_site_delete','--input','-',payload={'api_version':'1','command':'library.delete','library_id':site['id'],'base_version':1})
        back=run('library','restore','--request-id','cli_site_restore','--input','-',payload={'api_version':'1','command':'library.restore','library_id':site['id'],'base_version':gone['version']})
        self.assertEqual(back['kind'],'website')


    def test_http_view_is_workspace_scoped_and_read_only(self):
        import http.client
        import threading
        from yuplus.gateway import GatewayServer
        saved=self.write('add',name='HTTP 案例',url=URL)
        server=GatewayServer(self.data,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            connection.request('GET','/api/view');response=connection.getresponse()
            self.assertEqual(response.status,200)
            self.assertEqual(json.loads(response.read())['case_libraries'][0]['id'],saved['id'])
            connection.request('POST','/api/view',body='{}');response=connection.getresponse()
            self.assertEqual(response.status,405);response.read();connection.close()
            self.assertEqual(len(self.app.execute('library.list')['data']['libraries']),1)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_contents_rejected_and_registry_does_not_create_materials(self):
        for field,value in [('body','正文'),('files',[{'path':'case.pdf'}]),('index',{}),('children',[])]:
            with self.subTest(field=field),self.assertRaises(YuError):
                self.write('add',name='不能保存内容',url=URL,**{field:value})
        row=self.write('add',name='仅登记',url=URL)
        self.write('delete',library_id=row['id'],base_version=1)
        self.write('restore',library_id=row['id'],base_version=2)
        for table in ['sources','source_versions','blobs','source_files','objects']:
            self.assertEqual(self.app.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        self.assertFalse((self.data/'objects').exists())
        self.assertEqual(self.app.execute('library.show',{'library_id':row['id']})['meta']['library_policy']['lookup'],'on_demand_by_kind')

    def test_website_lifecycle_validation_backup_and_no_materials(self):
        url='https://Example.com:443/cases/?tag=art#selected'
        row=self.write('add',kind='website',name='网站案例',url=url)
        self.assertEqual(row['kind'],'website')
        self.assertEqual(row['url'],'https://example.com/cases/?tag=art#selected')
        with self.assertRaises(YuError):self.write('add',kind='website',name='重复',url=row['url'])
        updated=self.write('update',library_id=row['id'],base_version=1,name='新网站名称',url=row['url'])
        self.assertEqual(updated['kind'],'website')
        with read_snapshot(self.data) as db:
            self.assertEqual(browser_view(db,self.data)['case_libraries'][0]['kind'],'website')
        self.write('delete',library_id=row['id'],base_version=2)
        self.assertEqual(self.app.execute('library.list')['data']['libraries'],[])
        restored=self.write('restore',library_id=row['id'],base_version=3)
        self.assertEqual(restored['kind'],'website')
        backup=self.root/'web-backup';create_backup(self.data,backup)
        target=self.root/'web-restored';restore_backup(backup,target)
        with read_snapshot(target) as db:
            self.assertEqual(browser_view(db,target)['case_libraries'][0]['kind'],'website')
        for table in ['sources','source_versions','blobs','objects']:
            self.assertEqual(self.app.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        for bad in ['',None,'javascript:alert(1)','file:///tmp/example','https://user:pass@example.com','https://example.com:bad','https://exa mple.com']:
            with self.subTest(url=bad),self.assertRaises(YuError):self.write('add',kind='website',name='无效',url=bad)
        with self.assertRaises(YuError):self.write('add',kind='unknown',name='无效',url='https://example.com')
        http=self.write('add',kind='website',name='HTTP',url='http://example.org:80')
        self.assertEqual(http['url'],'http://example.org/')

    def test_schema_four_migration_keeps_folder_identity_and_backup(self):
        legacy=self.root/'legacy4';old=App(legacy)
        row=old.execute('library.add',{'api_version':'1','command':'library.add','name':'旧文件夹','url':URL},request_id='folder')['data']
        project=old.execute('project.create',{'name':'旧项目'},request_id='old_project')['data']['project_id']
        old.db.execute('ALTER TABLE case_libraries DROP COLUMN kind')
        old.db.execute('PRAGMA user_version=4');old.close()
        migrated=App(legacy)
        try:
            saved=migrated.execute('library.show',{'library_id':row['id']})['data']
            self.assertEqual(saved['kind'],'feishu_folder')
            self.assertEqual(saved['version'],row['version'])
            self.assertEqual(migrated.execute('project.show',project_id=project)['data']['name'],'旧项目')
            self.assertEqual(migrated.execute('doctor')['data']['schema_version'],5)
        finally:migrated.close()
        backups=list((self.root/'legacy4-migration-backups').iterdir());self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]/'yuplus.sqlite') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)
            self.assertNotIn('kind',[r[1] for r in db.execute('PRAGMA table_info(case_libraries)')])
