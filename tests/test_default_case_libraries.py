"""Bundled source registrations are installed once, without overriding user choices."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from yuplus.app import App
from yuplus.case_library import _DEFAULTS, _DEFAULT_RECEIPT
from yuplus.core import YuError
from yuplus.backup import create_backup, restore_backup


class DefaultLibraryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.data=self.root/'data'

    def read(self, path=None):
        app=App(path or self.data)
        try:return app.execute('library.list',{'include_deleted':True})['data']['libraries']
        finally:app.close()

    def test_first_use_exact_manifest_and_parallel_reopen(self):
        entries=json.loads(_DEFAULTS.read_text())['libraries']
        rows=self.read()
        self.assertEqual(len(rows),18)
        self.assertEqual(sum(r['kind']=='website' for r in rows),17)
        self.assertEqual({(r['kind'],r['name'],r['url']) for r in rows},
                         {(r['kind'],r['name'],r['url']) for r in entries})
        self.assertTrue(all(r['version']==1 and r['deleted_at'] is None for r in rows))
        with ThreadPoolExecutor(max_workers=4) as pool:
            for same in pool.map(lambda _:self.read(),range(4)):self.assertEqual(same,rows)
        with sqlite3.connect(self.data/'yuplus.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM case_library_requests WHERE request_id=?',(_DEFAULT_RECEIPT,)).fetchone()[0],1)
            for table in ('projects','sources','source_versions','blobs','objects'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)

    def test_existing_registration_and_user_changes_survive_restart_and_restore(self):
        entries=json.loads(_DEFAULTS.read_text())['libraries']
        with patch('yuplus.case_library.initialize_defaults'):
            app=App(self.data)
        def write(action,key,**fields):
            return app.execute('library.'+action,{'api_version':'1','command':'library.'+action,**fields},request_id=key)['data']
        own=write('add','one',**{**entries[0],'name':'公司自己的名称'})
        removed=write('add','two',**entries[1])
        removed=write('delete','delete',library_id=removed['id'],base_version=1)
        app.close()
        app=App(self.data)
        self.assertEqual(app.execute('library.show',{'library_id':own['id']})['data'],own)
        self.assertEqual(app.execute('library.show',{'library_id':removed['id']})['data'],removed)
        self.assertEqual(len(app.execute('library.list')['data']['libraries']),17)
        changed=write('update','change',library_id=own['id'],base_version=1,name='新的入口',url='https://team.feishu.cn/drive/folder/NewFolder')
        app.close()
        rows=self.read()
        self.assertEqual(len(rows),18)  # Original URL is not added again after editing.
        self.assertEqual(next(r for r in rows if r['id']==own['id']),changed)
        backup=self.root/'backup';create_backup(self.data,backup)
        restored=self.root/'restored';restore_backup(backup,restored)
        self.assertEqual(self.read(restored),rows)

    def test_invalid_bundle_rolls_back_entire_seed_and_can_retry(self):
        with patch('yuplus.case_library.initialize_defaults'):
            app=App(self.data);app.close()
        entries=json.loads(_DEFAULTS.read_text())['libraries']
        invalid=self.root/'invalid.json'
        invalid.write_text(json.dumps({'libraries':[entries[0],{**entries[1],'url':'javascript:bad'}]}))
        with patch('yuplus.case_library._DEFAULTS',invalid),self.assertRaises(YuError):App(self.data)
        with sqlite3.connect(self.data/'yuplus.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM case_libraries').fetchone()[0],0)
            self.assertFalse(db.execute('SELECT 1 FROM case_library_requests WHERE request_id=?',(_DEFAULT_RECEIPT,)).fetchone())
        self.assertEqual(len(self.read()),18)
