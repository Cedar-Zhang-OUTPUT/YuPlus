"""Guidance reaches the Agent and survives migrations, edits and source lifecycle."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from yuplus.app import App
from yuplus.case_library import catalog, _DEFAULTS
from yuplus.core import YuError
from yuplus.backup import create_backup, restore_backup


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.data = self.root / 'data'
        self.app = App(self.data); self.addCleanup(lambda: self.app.close()); self.seq = 0

    def write(self, action, **fields):
        self.seq += 1
        return self.app.execute('library.' + action, {'api_version':'1', 'command':'library.' + action, **fields}, request_id=f'guidance_{self.seq}')['data']

    def test_all_defaults_have_guidance_in_list_show_and_browser(self):
        rows = self.app.execute('library.list')['data']['libraries']
        entries = {r['url']:r for r in json.loads(_DEFAULTS.read_text())['libraries']}
        self.assertEqual(len(rows),31)
        for row in rows:
            for key in ('description', 'search_guidance'):
                self.assertTrue(row[key]); self.assertEqual(row[key], entries[row['url']][key])
            self.assertEqual(row,self.app.execute('library.show',{'library_id':row['id']})['data'])
            browser = next(r for r in catalog(self.app.db) if r['id']==row['id'])
            self.assertEqual(row['search_guidance'],browser['search_guidance'])
        self.assertTrue(all(e['guidance_sources'] for e in entries.values()))

    def test_personal_edits_omission_clear_replay_and_backup(self):
        row = self.write('add', kind='website', name='Personal', url='https://example.com/', description=' 光影装置 ', search_guidance='light / installation\n核对现场视频')
        self.assertEqual(row['description'],'光影装置')
        fields = {'library_id':row['id'], 'base_version':1, 'name':row['name'], 'url':row['url']}
        changed = self.write('update',**fields,description='')
        self.assertEqual(changed['description'],''); self.assertEqual(changed['search_guidance'],row['search_guidance'])
        replay = self.app.execute('library.update',{'api_version':'1','command':'library.update',**fields,'description':''},request_id='guidance_2')
        self.assertTrue(replay['meta']['replayed']);self.assertEqual(replay['data'],changed)
        with self.assertRaises(YuError):self.write('update',**fields,search_guidance='stale')
        self.write('delete',library_id=row['id'],base_version=2)
        self.assertNotIn(row['id'],[r['id'] for r in self.app.execute('library.list')['data']['libraries']])
        restored=self.write('restore',library_id=row['id'],base_version=3)
        self.assertEqual(restored['search_guidance'],row['search_guidance'])
        create_backup(self.data,self.root/'backup');restore_backup(self.root/'backup',self.root/'restore')
        app=App(self.root/'restore')
        try:self.assertEqual(app.execute('library.show',{'library_id':row['id']})['data'],restored)
        finally:app.close()

    def test_invalid_guidance_is_atomic_and_explicit_default_clear_wins(self):
        for key,limit in [('description',1000),('search_guidance',2000)]:
            for value in [None,[],{},17,'x'*(limit+1),'nul\x00text']:
                with self.subTest(key=key,value=type(value)),self.assertRaises(YuError):
                    self.write('add',kind='website',name='Bad',url='https://example.com/',**{key:value})
        self.assertEqual(len(self.app.execute('library.list')['data']['libraries']),31)
        row=self.app.execute('library.list')['data']['libraries'][0]
        changed=self.write('update',library_id=row['id'],base_version=1,name=row['name'],url=row['url'],description='',search_guidance='自己的建议')
        self.assertEqual(changed['description'],'')
        self.assertEqual(next(r for r in catalog(self.app.db) if r['id']==row['id'])['search_guidance'],'自己的建议')
        self.app.close();self.app=App(self.data)
        self.assertEqual(self.app.execute('library.show',{'library_id':row['id']})['data'],changed)

    def test_schema10_upgrade_preserves_rows_and_receipts_without_reenabling(self):
        row=self.app.execute('library.list')['data']['libraries'][0]
        self.write('delete',library_id=row['id'],base_version=1)
        self.write('add',kind='website',name='Old Personal',url='https://example.com/')
        for key in ('description','search_guidance'):self.app.db.execute('ALTER TABLE case_libraries DROP COLUMN '+key)
        self.app.db.execute('PRAGMA user_version=10')
        before=[dict(r) for r in self.app.db.execute('SELECT * FROM case_libraries')]
        receipts=[tuple(r) for r in self.app.db.execute('SELECT * FROM case_library_requests')]
        self.app.close();self.app=App(self.data)
        self.assertEqual(self.app.execute('doctor')['data']['schema_version'],11)
        self.assertEqual(receipts,[tuple(r) for r in self.app.db.execute('SELECT * FROM case_library_requests')])
        for saved in before:
            current=dict(self.app.db.execute('SELECT * FROM case_libraries WHERE id=?',(saved['id'],)).fetchone())
            self.assertEqual({k:current[k] for k in saved},saved)
        rows=self.app.execute('library.list')['data']['libraries'];self.assertEqual(len(rows),31)
        self.assertNotIn(row['id'],[r['id'] for r in rows])
        self.assertTrue(self.app.execute('library.show',{'library_id':row['id']})['data']['search_guidance'])
        own=next(r for r in rows if r['name']=='Old Personal');self.assertEqual(own['description'],'')
        backups=list((self.root/'data-migration-backups').iterdir());self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]/'yuplus.sqlite') as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],10)
        self.app.close();self.app=App(self.data)
        self.assertEqual(len(list((self.root/'data-migration-backups').iterdir())),1)
