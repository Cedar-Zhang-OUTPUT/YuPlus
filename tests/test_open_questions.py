import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from yuplus.app import App, CONTRACTS
from yuplus.core import YuError
from yuplus.browser_view import browser_view, read_snapshot
from yuplus.backup import create_backup, restore_backup
from yuplus.export_bundle import prepare_bundle


class LegacyApp(App):
    def _initialize(self):
        self.db.executescript((CONTRACTS/'schema.sql').read_text())
        self.db.executescript((CONTRACTS/'monitor-schema.sql').read_text())


class OpenQuestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.app=App(self.root/'data');self.addCleanup(self.app.close)
        self.pid=self.app.execute('project.create',{'name':'探索项目'},request_id='p')['data']['project_id'];self.seq=0

    def write(self, data, typ='open_questions', old=None, app=None, pid=None):
        self.seq+=1;op={'op_id':'question','type_key':typ,'scope_key':'project','base_revision':old['revision_id'] if old else None,
          'set_items':[{'item_id':'q1','data':data,'epistemic_kind':'suggestion','source_refs':[],'dependencies':[]}]}
        if old:op['object_id']=old['object_id']
        return (app or self.app).execute('draft.apply',{'api_version':'1','command':'draft.apply','reason':'维护问题','objects':[op],'decisions':[]},project_id=pid or self.pid,request_id=f'write{self.seq}')

    def test_open_question_lifecycle_remains_separate_from_qa_and_drives_review(self):
        created=self.write({'question':'如何让展览更有参与感？','context':'主策与会议共同提出','impact':'影响互动方向','options':['参与式共创','收集观众故事'],'status':'exploring'})
        obj=created['data']['objects'][0]
        qa=self.write({'question':'客户询问能否缩短影片','asked_by':'客户','answer':'团队建议保留两分钟核心段落','answered_by':'策划团队','status':'answered'},typ='qa')['data']['objects'][0]
        dep={'dependency_id':'q','object_id':obj['object_id'],'revision_id':obj['revision_id'],'item_id':'q1','kind':'fact'}
        request={'api_version':'1','command':'review.publish','reason':'整理待讨论方向','documents':[{'target':{'type_key':'advancement','scope_key':'project'},'base_revision':None,'read_basis':[{'object_id':obj['object_id'],'revision_id':obj['revision_id']}],'structure_cause_change_ids':[],'set_blocks':[{'block_id':'discussion','markdown':'讨论参与方式','dependencies':[dep],'cause_change_ids':[]}]}]}
        review=self.app.execute('review.publish',request,project_id=self.pid,request_id='review1')['data']['documents'][0]
        changed=self.write({'question':'如何让展览更有参与感？','status':'resolved','conclusion':'先开展观众故事调研','related_object_ids':[qa['object_id']]},old=obj)
        new=changed['data']['objects'][0]
        request['documents'][0].update({'target':{'object_id':review['object_id'],'type_key':'advancement','scope_key':'project'},'base_revision':review['revision_id'],'read_basis':[{'object_id':new['object_id'],'revision_id':new['revision_id']}]})
        block=request['documents'][0]['set_blocks'][0];block.update(markdown='推进观众故事调研',dependencies=[{**dep,'revision_id':new['revision_id']}])
        with self.assertRaises(YuError) as missing_cause:self.app.execute('review.publish',request,project_id=self.pid,request_id='without_cause')
        self.assertEqual(missing_cause.exception.code,'DRAFT_CHANGE_REQUIRED')
        block['cause_change_ids']=[changed['meta']['change_id']]
        self.app.execute('review.publish',request,project_id=self.pid,request_id='review2')
        with read_snapshot(self.root/'data') as db:view=browser_view(db,self.root/'data',self.pid)
        self.assertEqual(next(t for t in view['catalog']['objects'] if t['type_key']=='open_questions')['code'],'D25')
        self.assertEqual(len([o for o in view['objects'] if o['type_key']=='qa']),1)
        self.assertEqual(len([r for r in view['object_revisions'] if r['object_id']==obj['object_id']]),2)
        manifest=prepare_bundle(self.root/'data',self.pid,self.root/'export')
        self.assertEqual([o['type_key'] for o in manifest['shared_qa']],['qa'])
        self.assertIn('如何让展览更有参与感', (self.root/'export/review.md').read_text())

    def test_validation_and_cross_project_relations_are_atomic(self):
        for data in [{'question':'议题','status':'answered'},{'question':'议题','answer':'不是客户答复'},{'question':'议题','options':'字符串不是列表'}]:
            with self.assertRaises(YuError):self.write(data)
        other=self.app.execute('project.create',{'name':'另一个项目'},request_id='other')['data']['project_id']
        foreign=self.write({'question':'其他项目'},pid=other)['data']['objects'][0]
        with self.assertRaises(YuError) as exc:self.write({'question':'越界关联','related_object_ids':[foreign['object_id']]})
        self.assertEqual(exc.exception.code,'CROSS_PROJECT_REFERENCE')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM objects WHERE project_id=?',(self.pid,)).fetchone()[0],0)

    def test_schema_two_upgrade_preserves_rows_and_constraints_and_backup(self):
        path=self.root/'legacy';old=LegacyApp(path)
        pid=old.execute('project.create',{'name':'旧项目'},request_id='p')['data']['project_id']
        original=self.write({'question':'旧客户问题','answer':'原答复'},typ='qa',app=old,pid=pid)['data']['objects'][0]
        from yuplus.monitor import Monitor
        from test_monitor import FakeReader
        monitor=Monitor(old,FakeReader())
        monitor.execute('add',{'chat_id':'oc_test'},pid)
        old.execute('review.publish',{'api_version':'1','command':'review.publish','reason':'旧版引用',
            'documents':[{'target':{'type_key':'debrief','scope_key':'project'},'base_revision':None,
              'read_basis':[{'object_id':original['object_id'],'revision_id':original['revision_id']}],
              'structure_cause_change_ids':[], 'set_blocks':[{'block_id':'qa','markdown':'客户已回复',
                'dependencies':[{'dependency_id':'qa','object_id':original['object_id'],'revision_id':original['revision_id'],'item_id':'q1','kind':'fact'}],'cause_change_ids':[]}]}]},
            project_id=pid,request_id='legacyreview')
        tables=[r[0] for r in old.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        before={t:[tuple(r) for r in old.db.execute('SELECT * FROM '+t)] for t in tables};old.close()
        upgraded=App(path)
        try:
            self.assertEqual(upgraded.db.execute('PRAGMA user_version').fetchone()[0],10)
            self.assertEqual(upgraded.db.execute('PRAGMA foreign_keys').fetchone()[0],1)
            self.assertEqual(upgraded.db.execute('PRAGMA foreign_key_check').fetchall(),[])
            for t,rows in before.items():self.assertEqual([tuple(r) for r in upgraded.db.execute('SELECT * FROM '+t)],rows)
            self.write({'question':'新议题'},app=upgraded,pid=pid)
            with self.assertRaises(sqlite3.IntegrityError):upgraded.db.execute("UPDATE objects SET type_key='open_questions' WHERE id=?",(original['object_id'],))
            with self.assertRaises(sqlite3.IntegrityError):upgraded.db.execute("UPDATE object_revisions SET payload_json='{}' WHERE id=?",(original['revision_id'],))
        finally:upgraded.close()
        backups=list((self.root/'legacy-migration-backups').iterdir());self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]/'yuplus.sqlite') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM objects').fetchone()[0],2)
        backup=self.root/'backup';create_backup(path,backup);restore_backup(backup,self.root/'restored')
        restored=App(self.root/'restored')
        try:self.assertEqual(restored.db.execute("SELECT count(*) FROM objects WHERE type_key='open_questions'").fetchone()[0],1)
        finally:restored.close()

    def test_failed_rebuild_rolls_back_schema_and_data(self):
        path=self.root/'interrupted';old=LegacyApp(path)
        pid=old.execute('project.create',{'name':'迁移失败仍保留'},request_id='p')['data']['project_id']
        self.write({'question':'保留问答','answer':'保留答案'},typ='qa',app=old,pid=pid)
        before=list(old.db.iterdump());old.close()
        from yuplus.migrations import add_open_questions
        def fail_after_rebuild(db):
            add_open_questions(db)
            raise RuntimeError('injected after table rebuild')
        with patch('yuplus.migrations.add_open_questions',side_effect=fail_after_rebuild):
            with self.assertRaisesRegex(RuntimeError,'injected'):App(path)
        with sqlite3.connect(path/'yuplus.sqlite') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
            self.assertEqual(list(db.iterdump()),before)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        retried=App(path)
        try:self.write({'question':'重试可保存开放议题'},app=retried,pid=pid)
        finally:retried.close()
