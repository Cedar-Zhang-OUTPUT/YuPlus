import copy
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yuplus.app import App
from yuplus.backup import create_backup,restore_backup,verify_backup
from yuplus.browser_view import open_verified_asset,read_snapshot,registered_asset
from yuplus.core import YuError
from yuplus.source_check import scan
from yuplus.cli import default_data_dir,main
import test_gateway


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.f=test_gateway.GatewayTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_online_wal_and_external_assets_restore_without_original(self):
        result,path=self.f.source('external');content=path.read_bytes()
        copied,_=self.f.source('copy')
        backup=self.f.root/'backup';dest=self.f.root/'restored'
        create_backup(self.f.data,backup)
        path.unlink()
        restore_backup(backup,dest)
        with read_snapshot(dest) as db:
            asset=registered_asset(db,self.f.pid,result['snapshot_id'],'asset_original')
            stream,_=open_verified_asset(dest,asset)
            with stream:self.assertEqual(stream.read(),content)
            self.assertEqual(len(db.execute('SELECT id FROM projects').fetchall()),2)
        restored=App(dest)
        try:
            shown=restored.execute('source.show',{'source_id':result['source_id']},project_id=self.f.pid)['data']
            self.assertEqual(shown['snapshot']['assets'][0]['availability'],'available')
        finally:restored.close()
        # A restored database can itself be backed up independently of the original path.
        create_backup(dest,self.f.root/'second')
        with self.assertRaises(FileExistsError):restore_backup(backup,dest)
    def test_tamper_and_missing_asset_rejected(self):
        self.f.source('copy');backup=self.f.root/'backup';create_backup(self.f.data,backup)
        manifest=json.loads((backup/'backup.json').read_text());name=next(n for n in manifest['files'] if n.startswith('objects/'))
        (backup/name).write_bytes(b'bad')
        with self.assertRaises(YuError):verify_backup(backup)
        with self.assertRaises(YuError):restore_backup(backup,self.f.root/'bad_restore')
        self.assertFalse((self.f.root/'bad_restore').exists())
    def test_mapping_must_be_hashed_and_copied(self):
        self.f.source('external');backup=self.f.root/'backup';create_backup(self.f.data,backup)
        manifest=json.loads((backup/'backup.json').read_text());manifest['files'].pop('restored-assets.json')
        (backup/'backup.json').write_text(json.dumps(manifest))
        with self.assertRaises(YuError):verify_backup(backup)

    def test_external_changed_backup_fails_without_partial_output(self):
        _,path=self.f.source('external');path.write_bytes(b'new')
        with self.assertRaises(YuError):create_backup(self.f.data,self.f.root/'backup')
        self.assertFalse((self.f.root/'backup').exists())


class SourceCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.app=App(self.root);self.addCleanup(self.app.close)
        self.pid=self.app.execute('project.create',{'name':'checks'},request_id='project')['data']['project_id']
        self.payload={'api_version':'1','command':'source.import','target':{'mode':'create','provider':'feishu','resource_type':'docx','provider_key':'Token','canonical_url':'https://example.feishu.cn/docx/Token'},'snapshot':{'title':'remote','provider_revision':'4','captured_at':'2026-10-16T01:00:00Z','capture_scope':{'kind':'whole_resource'},'extraction_profile':'test','body':{'format':'text','text':'original'},'provenance':{'method':'test'}},'advance_head':True,'reason':'test'}
        self.saved=self.app.execute('source.import',self.payload,project_id=self.pid,request_id='source')['data']
    def remote(self,marker):return lambda source:{'kind':'revision','marker':marker,'token':'Token','resource_type':'docx'}
    def test_observation_never_rewrites_content(self):
        before=self.app.cursor(self.pid)
        self.assertEqual(scan(self.root,self.pid,observer=self.remote('4'))['checks'][0]['observation']['conclusion'],'unchanged')
        result=scan(self.root,self.pid,observer=self.remote('5'))
        self.assertEqual(result['changed'],1)
        self.assertEqual(self.app.cursor(self.pid),before)
        self.assertEqual(self.app.db.execute('SELECT body_text FROM source_versions').fetchone()[0],'original')
    def test_errors_not_unchanged_and_no_secret_persisted(self):
        def fail(source):raise YuError('FEISHU_UNAVAILABLE','auth failed')
        result=scan(self.root,self.pid,observer=fail)
        self.assertEqual(result['errors'],1)
        self.assertIsNone(result['checks'][0]['observation'])
    def test_failed_check_preserves_pending_update(self):
        observer=lambda source:{'kind':'modified_time','marker':'mtime:1','token':'Token','resource_type':'sheet'}
        scan(self.root,self.pid,observer=observer)
        newer=lambda source:{'kind':'modified_time','marker':'mtime:2','token':'Token','resource_type':'sheet'}
        scan(self.root,self.pid,observer=newer)
        def fail(source):raise YuError('FEISHU_UNAVAILABLE','offline')
        scan(self.root,self.pid,observer=fail)
        self.assertEqual(scan(self.root,self.pid,observer=newer)['changed'],1)

    def test_import_race_discards_old_observation(self):
        def race(source):
            request=copy.deepcopy(self.payload)
            request['target']={'mode':'append','source_id':self.saved['source_id'],'base_snapshot_id':self.saved['snapshot_id']}
            request['snapshot']['provider_revision']='5';request['snapshot']['body']['text']='new'
            self.app.execute('source.import',request,project_id=self.pid,request_id='update')
            return self.remote('4')(source)
        result=scan(self.root,self.pid,observer=race)
        self.assertFalse(result['checks'][0]['applied'])
    def test_unknown_marker_baseline_stays_unknown_then_changed(self):
        def remote(marker):return lambda source:{'kind':'modified_time','marker':marker,'token':'Token','resource_type':'sheet'}
        self.assertEqual(scan(self.root,self.pid,observer=remote('mtime:1'))['checks'][0]['observation']['conclusion'],'unknown')
        self.assertEqual(scan(self.root,self.pid,observer=remote('mtime:1'))['checks'][0]['observation']['conclusion'],'unknown')
        self.assertEqual(scan(self.root,self.pid,observer=remote('mtime:2'))['changed'],1)
        self.assertEqual(scan(self.root,self.pid,observer=remote('mtime:2'))['changed'],1)

    def test_same_content_recapture_updates_marker_without_rewriting_history(self):
        request=copy.deepcopy(self.payload)
        request['target'].update(resource_type='sheet',canonical_url='https://example.feishu.cn/sheets/SheetToken',provider_key='SheetToken')
        request['snapshot']['provider_revision']=None
        request['snapshot']['provenance']['remote_marker']='mtime:1'
        first=self.app.execute('source.import',request,project_id=self.pid,request_id='sheet')['data']
        def remote(source):return {'kind':'modified_time','marker':'mtime:2','token':'SheetToken','resource_type':'sheet'}
        self.assertEqual(scan(self.root,self.pid,first['source_id'],observer=remote)['changed'],1)
        request['target']={'mode':'append','source_id':first['source_id'],'base_snapshot_id':first['snapshot_id']}
        request['snapshot']['provenance']['remote_marker']='mtime:2'
        second=self.app.execute('source.import',request,project_id=self.pid,request_id='sheet-update')['data']
        self.assertFalse(second['snapshot_reused'])
        self.assertEqual(scan(self.root,self.pid,first['source_id'],observer=remote)['checks'][0]['observation']['conclusion'],'unchanged')
        old=self.app.db.execute('SELECT provenance_json FROM source_versions WHERE id=?',(first['snapshot_id'],)).fetchone()[0]
        self.assertEqual(json.loads(old)['remote_marker'],'mtime:1')
        request['target']['base_snapshot_id']=second['snapshot_id']
        self.assertTrue(self.app.execute('source.import',request,project_id=self.pid,request_id='sheet-repeat')['data']['snapshot_reused'])


class InstallationLocationTests(unittest.TestCase):
    def test_installed_directory_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
            prefix=Path(tmp)/'venv'
            (Path(tmp)/'installation.json').write_text(json.dumps({'cli':str(prefix/'bin/yu'),'data_dir':str(Path(tmp)/'formal')}))
            with patch('sys.prefix',str(prefix)):
                self.assertEqual(default_data_dir(),str(Path(tmp)/'formal'))
                with patch.dict(os.environ,{'YUPLUS_DATA_DIR':str(Path(tmp)/'selected')}):
                    self.assertEqual(default_data_dir(),str(Path(tmp)/'selected'))
    def test_corrupt_receipt_fails_without_silently_creating_another_database(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),patch('sys.prefix',str(Path(tmp)/'venv')):
            (Path(tmp)/'installation.json').write_text('bad json')
            output=io.StringIO()
            with contextlib.redirect_stdout(output):code=main(['status','--json'])
            self.assertNotEqual(code,0)
            self.assertEqual(json.loads(output.getvalue())['error']['code'],'INVALID_INPUT')
            output=io.StringIO()
            with contextlib.redirect_stdout(output):code=main(['--data-dir',str(Path(tmp)/'explicit'),'status','--json'])
            self.assertEqual(code,0)
            self.assertEqual(json.loads(output.getvalue())['data']['data_dir'],str((Path(tmp)/'explicit').resolve()))

class ServiceTests(unittest.TestCase):
    def test_start_reuses_and_stop_only_owned_service(self):
        from yuplus.service import control,status
        with tempfile.TemporaryDirectory() as tmp:
            app=App(tmp);app.close()
            try:
                first=control(tmp,'start');second=control(tmp,'start')
                self.assertTrue(second['reused']);self.assertEqual(first['pid'],second['pid'])
                state=Path(tmp)/'service.json';saved=state.read_text();value=json.loads(saved)
                value['instance_id']='wrong';state.write_text(json.dumps(value))
                self.assertFalse(control(tmp,'stop')['running'])
                state.write_text(saved);self.assertTrue(status(tmp)['running'])
            finally:control(tmp,'stop')
            self.assertFalse(status(tmp)['running'])
