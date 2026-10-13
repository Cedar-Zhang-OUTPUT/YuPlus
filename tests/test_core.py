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
