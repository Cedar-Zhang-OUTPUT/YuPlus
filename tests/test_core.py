import tempfile
import unittest
from pathlib import Path
from yuplus.app import App
from yuplus.core import YuError

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name))
    def tearDown(self):
        self.app.close()
        self.temp.cleanup()
    def create(self, name='城市项目', key='project_1'):
        return self.app.execute('project.create', {'name':name}, request_id=key)
    def test_projects_persist_and_are_independent(self):
        a=self.create(); b=self.create('另一个项目','project_2')
        self.assertNotEqual(a['data']['project_id'],b['data']['project_id'])
        self.app.close(); self.app=App(Path(self.temp.name))
        self.assertEqual(len(self.app.execute('project.list')['data']['projects']),2)
        self.assertEqual(self.app.db.execute('PRAGMA journal_mode').fetchone()[0],'wal')
    def test_project_creation_replay_and_payload_conflict(self):
        a=self.create(); replay=self.create()
        self.assertEqual(a['data'],replay['data']);self.assertTrue(replay['meta']['replayed'])
        with self.assertRaises(YuError) as error:self.create('changed')
        self.assertEqual(error.exception.code,'IDEMPOTENCY_CONFLICT')
    def test_project_read_does_not_write_a_change(self):
        p=self.create()['data']['project_id']
        before=self.app.db.execute('SELECT count(*) FROM changes').fetchone()[0]
        self.assertEqual(self.app.execute('project.show',project_id=p)['data']['project_id'],p)
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM changes').fetchone()[0],before)
    def test_empty_project_name_is_rejected(self):
        with self.assertRaises(YuError) as error:self.create(' ')
        self.assertEqual(error.exception.code,'INVALID_INPUT')
    def test_write_requires_request_id(self):
        with self.assertRaises(YuError) as error:self.app.execute('project.create',{'name':'x'})
        self.assertEqual(error.exception.code,'INVALID_INPUT')
    def test_packaged_contracts_match_approved_artifacts(self):
        root=Path(__file__).resolve().parents[1]
        for name in ['schema.sql','cli-input.schema.json','object-types.json']:
            self.assertEqual((root/'src/yuplus/contracts'/name).read_bytes(),(root/'docs/superpowers/specs/contracts/v0.1'/name).read_bytes())

    def test_project_rename_versions_history_replay_and_noop(self):
        pid=self.create()['data']['project_id']
        other=self.create('其他项目','project_2')['data']['project_id']
        before=self.app.execute('project.show',project_id=pid)['data']
        args={'name':'  新项目名称  ','base_metadata_version':1}
        first=self.app.execute('project.rename',args,project_id=pid,request_id='rename_1')
        self.assertEqual(first['data']['name'],'新项目名称')
        self.assertEqual(first['data']['previous_name'],before['name'])
        self.assertEqual(first['data']['metadata_version'],2)
        current=self.app.execute('project.show',project_id=pid)['data']
        self.assertEqual(current['created_at'],before['created_at'])
        self.assertNotEqual(current['updated_at'],before['updated_at'])
        self.assertEqual(self.app.execute('project.show',project_id=other)['data']['name'],'其他项目')
        second=self.app.execute('project.rename',{'name':'最终名称','base_metadata_version':2},project_id=pid,request_id='rename_2')
        replay=self.app.execute('project.rename',args,project_id=pid,request_id='rename_1')
        self.assertTrue(replay['meta']['replayed'])
        self.assertEqual(replay['data'],first['data'])
        self.assertEqual(self.app.execute('project.show',project_id=pid)['data']['name'],'最终名称')
        before_noop=self.app.execute('project.show',project_id=pid)['data']
        noop=self.app.execute('project.rename',{'name':'最终名称','base_metadata_version':3},project_id=pid,request_id='rename_noop')
        self.assertEqual(noop['data']['effect'],'noop')
        self.assertEqual(noop['data']['metadata_version'],3)
        self.assertEqual(self.app.execute('project.show',project_id=pid)['data'],before_noop)
        history=self.app.db.execute("SELECT changed_refs_json,reason FROM changes WHERE id=?",(second['meta']['change_id'],)).fetchone()
        self.assertIn('新项目名称',history['changed_refs_json'])
        self.assertIn('最终名称',history['reason'])
        self.app.close();self.app=App(Path(self.temp.name))
        self.assertEqual(self.app.execute('project.show',project_id=pid)['data']['name'],'最终名称')

    def test_project_rename_rejects_invalid_or_stale_requests_atomically(self):
        pid=self.create()['data']['project_id']
        valid={'name':'新名称','base_metadata_version':1}
        cases=[({},'INVALID_INPUT'), ({'name':'  ','base_metadata_version':1},'INVALID_INPUT'),
               ({'name':42,'base_metadata_version':1},'INVALID_INPUT'),
               ({'name':'新','base_metadata_version':True},'INVALID_INPUT'),
               ({'name':'新','base_metadata_version':0},'INVALID_INPUT'),
               ({**valid,'unexpected':'x'},'INVALID_INPUT'),
               ({**valid,'base_metadata_version':2},'BASE_REVISION_CONFLICT')]
        before=self.app.execute('project.show',project_id=pid)['data']
        for payload,code in cases:
            with self.subTest(payload=payload),self.assertRaises(YuError) as err:
                self.app.execute('project.rename',payload,project_id=pid,request_id='rename_invalid')
            self.assertEqual(err.exception.code,code)
        for target,request,code in [(None,'rename_missing','INVALID_INPUT'),('prj_missing','rename_missing','PROJECT_NOT_FOUND'),(pid,None,'INVALID_INPUT')]:
            with self.assertRaises(YuError) as err:self.app.execute('project.rename',valid,project_id=target,request_id=request)
            self.assertEqual(err.exception.code,code)
        self.assertEqual(self.app.execute('project.show',project_id=pid)['data'],before)
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM changes').fetchone()[0],1)
        self.app.execute('project.rename',valid,project_id=pid,request_id='rename_once')
        with self.assertRaises(YuError) as err:
            self.app.execute('project.rename',{**valid,'name':'另一名称'},project_id=pid,request_id='rename_once')
        self.assertEqual(err.exception.code,'IDEMPOTENCY_CONFLICT')
        self.app.db.execute("UPDATE projects SET lifecycle='archived',archived_at=updated_at WHERE id=?",(pid,))
        with self.assertRaises(YuError) as err:
            self.app.execute('project.rename',{**valid,'base_metadata_version':2},project_id=pid,request_id='rename_archived')
        self.assertEqual(err.exception.code,'PROJECT_ARCHIVED')
