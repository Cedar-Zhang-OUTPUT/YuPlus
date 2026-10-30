"""Current object contracts and non-destructive upgrade from a schema-7 project."""
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from yuplus.app import App, CONTRACTS
from yuplus.core import Context, YuError, canonical, digest, insert, now, write_revision, is_fresh

ROOT = Path(__file__).resolve().parents[1]

class ObjectCatalogUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.data = self.root/'data'

    def app(self):
        app=App(self.data);self.addCleanup(app.close);return app

    def test_owners_and_qa_parties_roundtrip_and_reject_invalid_owners(self):
        app=self.app();pid=app.execute('project.create',{'name':'排期'},request_id='p')['data']['project_id']
        def save(data, key, typ='milestones', previous=None):
            op={'op_id':'item','type_key':typ,'scope_key':'project','base_revision':previous['revision_id'] if previous else None,
                'set_items':[{'item_id':'one','data':data,'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
            if previous:op['object_id']=previous['object_id']
            return app.execute('draft.apply',{'api_version':'1','command':'draft.apply','reason':'更新','objects':[op],'decisions':[]},project_id=pid,request_id=key)['data']['objects'][0]
        previous=None
        for n, owners in enumerate([None,[],['主策'],['主策','BD']]):
            data={'event':'交付','time_kind':'date','start':'2026-12-20'}
            if owners is not None:data['owners']=owners
            previous=save(data,'valid'+str(n),previous=previous)
            shown=app.execute('draft.show',{'object_id':previous['object_id']},project_id=pid)['data']
            self.assertEqual(shown['items'][0]['data'].get('owners'),owners)
        for n, value in enumerate(['主策',None,[''],[' '],[3],['BD','BD']]):
            with self.assertRaises(YuError):save({'event':'交付','owners':value},'invalid'+str(n),previous=previous)
        qa=save({'question':'含税吗？','asked_by':'客户','answered_by':'BD','follow_up_person':'主策'},'qa','qa')
        data=app.execute('draft.show',{'object_id':qa['object_id']},project_id=pid)['data']['items'][0]['data']
        self.assertEqual((data['asked_by'],data['answered_by'],data['follow_up_person']),('客户','BD','主策'))

    def test_current_catalog_and_skills_only_describe_available_types(self):
        app=self.app();catalog=app.execute('types.show')['data']
        self.assertEqual(len(catalog['objects']),25)
        for word in ['project_assessment','creator_brief','立项评估结果','创作者 Brief']:
            self.assertNotIn(word,canonical(catalog))
            for path in (ROOT/'skills').rglob('*.md'):
                self.assertNotIn(word,path.read_text(),str(path))
        schema=json.loads((CONTRACTS/'cli-input.schema.json').read_text())
        self.assertNotIn('project_assessment',canonical(schema));self.assertNotIn('creator_brief',canonical(schema))
        for typ in ['project_assessment','creator_brief']:
            with self.assertRaises(YuError):app.execute('types.show',{'type_key':typ})

    def test_schema7_upgrade_backs_up_archives_and_retains_evidence(self):
        legacy=self.root/'legacy-contracts';shutil.copytree(CONTRACTS,legacy)
        schema=(legacy/'schema.sql').read_text().replace("'client_meetings','qa',","'client_meetings','qa','project_assessment',").replace("'advancement','creative_review'","'advancement','creative_review','creator_brief'")
        (legacy/'schema.sql').write_text(schema)
        with patch('yuplus.app.CONTRACTS',legacy),patch('yuplus.migrations.retire_object_types'),patch('yuplus.migrations.collaborative_objects'),patch('yuplus.purge.migrate'),patch('yuplus.case_library.migrate_guidance'):
            old=App(self.data)
        pid=old.execute('project.create',{'name':'旧项目'},request_id='project')['data']['project_id']
        def legacy_object(oid,typ,layer,scope='project'):
            ctx=Context(old.db,self.data,pid,'change_'+oid)
            with old.db:
                insert(old.db,'objects',project_id=pid,id=oid,layer=layer,type_key=typ,scope_key=scope,created_at=now())
                payload={'title':'历史内容','items':[{'item_id':'i','data':{'note':'保留原始判断'},'epistemic_kind':'hypothesis'}],'item_order':['i']} if layer=='draft' else {'title':'历史文档','blocks':[{'block_id':'b','markdown':'保留原文'}],'block_order':['b']}
                result=write_revision(ctx,oid,payload)
                insert(old.db,'changes',id=ctx.change_id,project_id=pid,command=layer+'.apply',effect='changed',request_id=ctx.change_id,request_hash=digest({}),actor_json='{}',reason='旧版内容',causal_change_ids_json='[]',changed_refs_json='[]',result_json=canonical(result),created_at=now())
            return result
        # FK constraints are deferred until each explicit transaction completes.
        old.db.execute('BEGIN')
        assessment=legacy_object('old_assessment','project_assessment','draft')
        old.db.execute('BEGIN')
        brief=legacy_object('old_brief','creator_brief','review','creator:alice:round:first')
        old.db.execute('BEGIN')
        guide=legacy_object('old_guide','expression_guide','draft','review:old_brief')
        self.assertEqual(old.db.execute('PRAGMA user_version').fetchone()[0],7)
        original=old.db.execute('SELECT payload_json FROM object_revisions WHERE id=?',(assessment['revision_id'],)).fetchone()[0]
        old.close()
        current=self.app()
        self.assertEqual(current.execute('doctor')['data']['schema_version'],11)
        self.assertEqual(current.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertFalse(current.db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(current.execute('draft.list',project_id=pid)['data']['objects'],[])
        self.assertEqual(current.execute('review.list',project_id=pid)['data']['objects'],[])
        self.assertEqual(current.db.execute('SELECT payload_json FROM object_revisions WHERE id=?',(assessment['revision_id'],)).fetchone()[0],original)
        self.assertFalse(is_fresh(current.db,pid,assessment['revision_id'],'i'))
        for layer, oid, result in [('draft','old_assessment',assessment),('review','old_brief',brief),('draft','old_guide',guide)]:
            with self.assertRaises(YuError) as err:
                current.execute(layer+'.restore',{'api_version':'1','command':layer+'.restore','object_id':oid,'base_revision':result['revision_id'],'reason':'恢复'},project_id=pid,request_id='restore_'+oid)
            self.assertEqual(err.exception.code,'INVALID_SCOPE')
        with self.assertRaises(sqlite3.IntegrityError):current.db.execute("UPDATE objects SET archived_at=NULL WHERE id='old_brief'")
        backups=list(self.root.glob('data-migration-backups/*/yuplus.sqlite'))
        self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],7)
            self.assertIsNone(db.execute("SELECT archived_at FROM objects WHERE id='old_brief'").fetchone()[0])
        again=App(self.data);again.close()
        self.assertEqual(len(list(self.root.glob('data-migration-backups/*/yuplus.sqlite'))),1)
