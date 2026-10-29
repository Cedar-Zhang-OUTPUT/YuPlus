"""Hard-delete acceptance: real CLI/SQLite/file pool, disposable fixtures only."""
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_cli as cli
from yuplus.app import App
from yuplus.core import YuError
from yuplus.backup import create_backup, restore_backup, verify_backup
from yuplus.purge import storage_lock

class PurgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cli.CliAcceptanceTests.setUpClass.__func__(cls)
        cls.output_validator.schema['oneOf'][0]['properties']['meta']['properties']['library_policy']={'type':'object'}
    setUp = cli.CliAcceptanceTests.setUp
    invoke = cli.CliAcceptanceTests.invoke
    project = cli.CliAcceptanceTests.project
    write = cli.CliAcceptanceTests.write
    initial_chain = cli.CliAcceptanceTests.initial_chain

    def preview(self, kind, pid=None, ident=None):
        p={} if kind=='project' else {('library_id' if kind=='library' else 'source_id' if kind=='source' else 'object_id'):ident}
        args=(kind,'purge')+ (('--project',pid) if pid else ())
        return p,self.invoke(*args,payload=p)['data']

    def purge(self, kind, pid=None, ident=None, request='purge', extra=None):
        p,plan=self.preview(kind,pid,ident)
        p.update(dry_run=False,plan_hash=plan['plan_hash'],confirm_id=plan['target_id'],reason='用户要求彻底删除')
        p.update(extra or {})
        args=(kind,'purge')+(('--project',pid) if pid else ())+('--request-id',request)
        return p,self.invoke(*args,payload=p)

    def asset(self,pid,storage='copy',name='original.pdf',key='asset'):
        original=Path(self.temp.name)/name;original.write_bytes(b'%PDF-test original material')
        p=cli.example('02-source-local.input.json')
        p['snapshot']['assets'][0].update(local_path=str(original),storage=storage)
        return original,self.write(pid,'source.import',p,key)

    def db(self):
        app=App(self.data_dir);self.addCleanup(app.close);return app

    def test_preview_and_confirmation_then_project_deletes_entire_chain(self):
        pid,source,draft,review,_=self.initial_chain()
        other=self.project('other','其他项目')['data']['project_id']
        p,plan=self.preview('project',pid)
        self.assertEqual(plan['records']['object_revisions'],2)
        self.assertTrue(plan['can_execute'])
        self.assertEqual(len(self.invoke('project','list')['data']['projects']),2)
        self.write(pid,'project.purge',{'dry_run':False},'bad',code=2)
        payload,result=self.purge('project',pid)
        self.assertTrue(result['data']['complete'])
        self.assertEqual([r['project_id'] for r in self.invoke('project','list','--include-deleted')['data']['projects']],[other])
        app=self.db();self.assertIsNone(app.db.execute('PRAGMA foreign_key_check').fetchone())
        for table in ('sources','source_versions','objects','object_revisions','changes','decisions'):
            self.assertEqual(app.db.execute(f'SELECT count(*) FROM {table} WHERE project_id=?',(pid,)).fetchone()[0],0)
        replay=self.write(pid,'project.purge',payload,'purge');self.assertTrue(replay['meta']['replayed'])
        self.assertEqual(self.invoke('project','create','--name','城市展项目','--request-id','project_first',code=5)['error']['code'],'RESOURCE_PURGED')
        with self.assertRaises(sqlite3.IntegrityError):app.db.execute('DELETE FROM projects WHERE id=?',(other,))

    def test_soft_deleted_project_can_be_purged(self):
        pid=self.project()['data']['project_id']
        self.invoke('project','delete','--project',pid,'--base-version','1','--request-id','hide')
        self.assertTrue(self.purge('project',pid)[1]['data']['complete'])

    def test_project_purge_cleans_board_cache_and_blocks_stale_refresh(self):
        from yuplus.case_preview import PreviewCache
        from tests.test_appearance import png
        pid=self.project()['data']['project_id'];app=self.db()
        row=app.execute('research.create',{'api_version':'1','command':'research.create','title':'研究'},project_id=pid,request_id='research')['data']
        row=app.execute('research.update',{'api_version':'1','command':'research.update','research_id':row['id'],
            'base_version':1,'document_url':'https://team.feishu.cn/docx/Doc1',
            'board_url':'https://team.feishu.cn/docx/Doc1#block1','board_token':'board1'},project_id=pid,request_id='bind')['data']
        root=Path(self.temp.name)/'cache'
        def runner(argv,**kwargs):
            Path(kwargs['cwd'],'preview.png').write_bytes(png());return {}
        def cache_factory(data_dir):return PreviewCache(data_dir,root=root,runner=runner)
        cache=cache_factory(self.data_dir);cache.refresh(row)
        unrelated=root/('a'*64+'_'+'b'*64);unrelated.write_bytes(png())
        with patch('yuplus.case_preview.PreviewCache',side_effect=cache_factory):
            preview=app.execute('project.purge',{},project_id=pid)['data']
            self.assertEqual(preview['preview_caches_to_clear'],1)
            result=app.execute('project.purge',{'dry_run':False,'plan_hash':preview['plan_hash'],
                'confirm_id':pid,'reason':'删除'},project_id=pid,request_id='purge_cache')['data']
        self.assertTrue(result['complete']);self.assertEqual(list(root.glob(cache.prefix(row)+'*')),[])
        self.assertTrue(unrelated.exists())
        with self.assertRaises(YuError) as caught:cache.refresh(row)
        self.assertEqual(caught.exception.code,'TARGET_NOT_FOUND')

    def test_reference_block_and_remove_consumers_before_source(self):
        pid,source,draft,review,review_payload=self.initial_chain()
        sid=source['data']['source_id'];did=draft['data']['objects'][0]['object_id'];rid=review['data']['documents'][0]['object_id']
        for kind,ident in [('source',sid),('draft',did)]:
            p,plan=self.preview(kind,pid,ident);self.assertFalse(plan['can_execute']);self.assertTrue(plan['blockers'])
            p.update(dry_run=False,plan_hash=plan['plan_hash'],confirm_id=ident,reason='删除')
            result=self.write(pid,kind+'.purge',p,'blocked_'+kind,code=5)
            self.assertEqual(result['error']['code'],'PURGE_REFERENCED')
        self.purge('review',pid,rid,request='review')
        self.purge('draft',pid,did,request='draft')
        self.purge('source',pid,sid,request='source')
        self.assertEqual(self.invoke('review','list','--project',pid,'--include-deleted')['data']['objects'],[])
        self.assertEqual(self.write(pid,'review.publish',review_payload,'review_initial')['data']['effect'],'purged')
        self.assertIsNone(self.db().db.execute('PRAGMA foreign_key_check').fetchone())

    def test_changed_plan_and_cross_project_are_rejected(self):
        pid=self.project()['data']['project_id'];p,plan=self.preview('project',pid)
        self.invoke('project','rename','--project',pid,'--name','已更名','--base-version','1','--request-id','rename')
        p.update(dry_run=False,confirm_id=pid,plan_hash=plan['plan_hash'],reason='删除')
        self.assertEqual(self.write(pid,'project.purge',p,'stale',code=4)['error']['code'],'BASE_REVISION_CONFLICT')
        other=self.project('other')['data']['project_id'];_,source=self.asset(pid)
        self.write(other,'source.purge',{'source_id':source['data']['source_id']},'cross',code=3)

    def test_shared_blob_retained_until_last_reference_external_original_untouched(self):
        a=self.project()['data']['project_id'];b=self.project('second')['data']['project_id']
        original,_=self.asset(a);self.asset(b)
        app=self.db();sha=app.db.execute('SELECT sha256 FROM blobs').fetchone()[0]
        path=self.data_dir/'objects/sha256'/sha[:2]/sha
        _,first=self.purge('project',a);self.assertEqual(first['data']['shared_files_retained'],1);self.assertTrue(path.exists())
        self.purge('project',b,request='purge_b');self.assertFalse(path.exists());self.assertTrue(original.exists())
        self.assertEqual(app.db.execute('SELECT count(*) FROM blobs').fetchone()[0],0)

    def test_cleanup_failure_is_resumable_and_never_reports_complete(self):
        pid=self.project()['data']['project_id'];self.asset(pid);p,plan=self.preview('project',pid)
        p.update(dry_run=False,plan_hash=plan['plan_hash'],confirm_id=pid,reason='删除')
        app=self.db();unlink=Path.unlink
        def denied(path,*a,**kw):
            if '/objects/sha256/' in str(path):raise PermissionError('read only fixture')
            return unlink(path,*a,**kw)
        with patch.object(Path,'unlink',denied):
            result=app.execute('project.purge',p,project_id=pid,request_id='cleanup')['data']
        self.assertFalse(result['complete']);self.assertEqual(result['files_pending'],1)
        replay=app.execute('project.purge',p,project_id=pid,request_id='cleanup')
        self.assertTrue(replay['meta']['replayed']);self.assertTrue(replay['data']['complete'])

    def test_purge_library_removes_old_payload_and_does_not_reseed(self):
        entries=self.invoke('library','list')['data']['libraries'];ident=entries[0]['id'];url=entries[0]['url']
        self.purge('library',ident=ident)
        self.assertNotIn(url,json.dumps(self.invoke('library','list','--include-deleted')))
        self.assertEqual(len(self.invoke('library','list')['data']['libraries']),len(entries)-1)
        self.invoke('library','show','--library',ident,code=5)
        self.assertFalse(self.preview('library',ident=entries[1]['id'])[1]['blockers'])
        from yuplus.case_library import catalog
        remaining=catalog(self.db().db)
        self.assertTrue(all(row['origin']=='official' for row in remaining))
        self.assertNotIn(ident,json.dumps(remaining))

    def test_storage_lock_blocks_source_import_and_purge(self):
        pid=self.project()['data']['project_id'];a=self.db();b=self.db()
        with storage_lock(a):
            for command,p in [('project.purge',{}),('source.import',cli.example('01-source-feishu.input.json'))]:
                with self.assertRaises(YuError) as err:b.execute(command,p,project_id=pid,request_id='lock')
                self.assertEqual(err.exception.code,'DATABASE_BUSY')

    def test_library_checks_references_across_projects(self):
        pid=self.project()['data']['project_id'];app=self.db()
        ident=app.db.execute('SELECT id FROM case_libraries LIMIT 1').fetchone()[0]
        app.db.execute('INSERT INTO case_research_requests VALUES(?,?,?,?)',
                       (pid,'reference','test',json.dumps({'library_id':ident})))
        preview=app.execute('library.purge',{'library_id':ident})['data']
        self.assertFalse(preview['can_execute'])
        self.assertTrue(any(r['table']=='case_research_requests' for r in preview['blockers']))

    def test_original_and_restored_external_files(self):
        pid=self.project()['data']['project_id'];original,source=self.asset(pid,'external')
        backup=Path(self.temp.name)/'backup';restore=Path(self.temp.name)/'restored'
        create_backup(self.data_dir,backup);restore_backup(backup,restore)
        restored=App(restore);self.addCleanup(restored.close)
        plan=restored.execute('project.purge',{},project_id=pid)['data']
        result=restored.execute('project.purge',{'dry_run':False,'confirm_id':pid,'plan_hash':plan['plan_hash'],'reason':'删除恢复副本'},project_id=pid,request_id='restored')['data']
        self.assertTrue(result['complete']);self.assertTrue(original.exists())
        self.assertEqual(list((restore/'external-files').iterdir()),[])
        self.assertEqual(json.loads((restore/'restored-assets.json').read_text()),{})
        verify_backup(backup)
        self.purge('source',pid,source['data']['source_id']);self.assertTrue(original.exists())

    def test_project_schedule_and_live_lease_guards(self):
        from yuplus.monitor import Monitor
        from tests.test_monitor import FakeReader
        pid=self.project()['data']['project_id'];app=self.db();monitor=Monitor(app,FakeReader())
        mid=monitor.execute('add',{'chat_id':'oc_test'},pid)['monitor_id']
        app.db.execute('UPDATE chat_monitors SET schedule_json=? WHERE id=?',(json.dumps({'automation_id':'task','state':'active'}),mid))
        p,plan=self.preview('project',pid);self.assertTrue(plan['scheduler_actions'])
        p.update(dry_run=False,plan_hash=plan['plan_hash'],confirm_id=pid,reason='删除')
        self.assertEqual(self.write(pid,'project.purge',p,'scheduled',code=5)['error']['code'],'PURGE_SCHEDULES_ACTIVE')
        self.purge('project',pid,extra={'schedulers_handled':True})
        self.assertEqual(app.db.execute('SELECT count(*) FROM chat_monitors').fetchone()[0],0)

    def test_failed_deletion_rolls_back_records_and_append_only_guards(self):
        pid=self.project()['data']['project_id'];app=self.db()
        app.db.execute('CREATE TABLE extra_reference (id TEXT PRIMARY KEY, target TEXT REFERENCES projects(id))')
        app.db.execute('INSERT INTO extra_reference VALUES(?,?)',('extra',pid))
        p,plan=self.preview('project',pid)
        p.update(dry_run=False,plan_hash=plan['plan_hash'],confirm_id=pid,reason='删除')
        self.assertEqual(self.write(pid,'project.purge',p,'rollback',code=70)['error']['code'],'INTEGRITY_FAILURE')
        self.assertIsNotNone(app.db.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone())
        self.assertEqual(app.db.execute('SELECT count(*) FROM purge_requests').fetchone()[0],0)
        with self.assertRaises(sqlite3.IntegrityError):app.db.execute('DELETE FROM projects WHERE id=?',(pid,))
        self.assertIsNone(app.db.execute('PRAGMA foreign_key_check').fetchone())

    def test_monitor_history_and_collaboration_are_purged_after_lease_released(self):
        from yuplus.monitor import Monitor
        from tests.test_monitor import FakeReader
        pid=self.project()['data']['project_id'];app=self.db();m=Monitor(app,FakeReader())
        mid=m.execute('add',{'chat_id':'oc_test'},pid)['monitor_id']
        auth=m.execute('begin',{'monitor_id':mid,'force':True},pid)
        m.execute('fetch',{'run_id':auth['run_id'],'token':auth['token'],'page_budget':10},pid)
        self.assertFalse(self.preview('project',pid)[1]['can_execute'])
        m.execute('pause',{'monitor_id':mid,'version':1},pid)
        with patch('yuplus.collaboration.fetch',return_value={'revision':1,'content':'<h1 id="heading">团队文档</h1>','reference_map':{}}):
            app.execute('collab.bind',{'url':'https://example.feishu.cn/docx/testDocument','mappings':{}},project_id=pid,request_id='bind')
            app.execute('collab.pull',{},project_id=pid)
        plan=self.preview('project',pid)[1]
        self.assertGreater(plan['records']['monitor_messages'],0)
        self.assertGreater(plan['records']['collaboration_events'],0)
        self.assertFalse(plan['requires_scheduler_handling'])
        self.purge('project',pid)
        for table in ['monitor_runs','monitor_messages','monitor_leases','monitor_steps','chat_monitors','collaboration_docs','collaboration_events','collaboration_operations']:
            self.assertEqual(app.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        self.assertIsNone(app.db.execute('PRAGMA foreign_key_check').fetchone())

    def test_schema9_migration_keeps_records_and_backup(self):
        pid=self.project()['data']['project_id'];app=self.db()
        for table in ['purge_requests','purge_tombstones','purged_requests']:app.db.execute('DROP TABLE '+table)
        app.db.execute('PRAGMA user_version=9')
        current=self.db()
        self.assertEqual(current.db.execute('PRAGMA user_version').fetchone()[0],10)
        self.assertEqual(current.db.execute('SELECT id FROM projects').fetchone()[0],pid)
        backups=list(self.data_dir.parent.glob('data-migration-backups/*'))
        self.assertEqual(len(backups),1);verify_backup(backups[0])
        with sqlite3.connect(backups[0]/'yuplus.sqlite') as old:self.assertEqual(old.execute('PRAGMA user_version').fetchone()[0],9)

if __name__=='__main__':unittest.main()
