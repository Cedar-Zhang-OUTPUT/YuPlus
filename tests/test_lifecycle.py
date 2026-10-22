"""Public CLI lifecycle checks against isolated persistent projects and provenance."""
import copy
from pathlib import Path
import json
from tests import test_cli as cli_tests
from yuplus.app import App
from yuplus.browser_view import browser_view
from yuplus.source_check import scan


class LifecycleTests(cli_tests.CliAcceptanceTests):
    # Reuse CLI fixture/helpers, without running the inherited acceptance cases twice.
    def lifecycle(self, pid, layer, action, ident, head, key, code=0, **extra):
        payload={'api_version':'1','command':f'{layer}.{action}','reason':'用户要求'+action,
                 'source_id' if layer=='source' else 'object_id':ident,
                 'base_snapshot_id' if layer=='source' else 'base_revision':head,**extra}
        return self.write(pid,payload['command'],payload,key,code=code)

    def guide(self,pid,source,review,request_id='guide',previous=None):
        target=review['data']['documents'][0]
        payload={'api_version':'1','command':'draft.apply','reason':'用户删除成果',
          'objects':[{'op_id':'guide','type_key':'expression_guide','scope_key':'review:'+target['object_id'],
            'base_revision':previous['revision_id'] if previous else None,
            'set_items':[{'item_id':'instruction','data':{'review_object_id':target['object_id'],'block_ids':['*'],
              'instruction':'用户要求删除本成果' if not previous else '用户要求重新整理成果','intent':'omit' if not previous else 'rewrite'},
              'epistemic_kind':'user_supplied','source_refs':[{'evidence_id':'user','source_version_id':source['data']['snapshot_id'],'kind':'instruction'}],'dependencies':[]}]}], 'decisions':[]}
        return self.write(pid,'draft.apply',payload,request_id)

    def prepare(self,pid,review):
        obj=review['data']['documents'][0]
        return self.invoke('review','prepare','--project',pid,payload={'api_version':'1','command':'review.prepare',
             'target':{'object_id':obj['object_id'],'type_key':'debrief','scope_key':'project'},'select_basis':[],'cause_change_ids':[]})['data']

    def test_source_delete_retains_citations_and_restores(self):
        pid,source,draft,review,_=self.initial_chain();sid=source['data']['source_id'];snap=source['data']['snapshot_id']
        before=self.invoke('source','show','--project',pid,'--source',sid,'--include-body')['data']['snapshot']
        result=self.lifecycle(pid,'source','delete',sid,snap,'hide_source')
        self.assertTrue(result['data']['archived']);self.assertTrue(result['data']['referenced_by'])
        self.assertEqual(self.invoke('source','list','--project',pid)['data']['sources'],[])
        self.assertEqual(self.invoke('source','list','--project',pid,'--include-deleted')['data']['sources'][0]['id'],sid)
        self.assertEqual(self.invoke('source','show','--project',pid,'--source',sid,'--include-body')['data']['snapshot'],before)
        called=[];self.assertEqual(scan(self.data_dir,project_id=pid,observer=lambda s:called.append(s))['checks'],[]);self.assertEqual(called,[])
        self.assertTrue(self.lifecycle(pid,'source','delete',sid,snap,'hide_source')['meta']['replayed'])
        self.lifecycle(pid,'source','restore',sid,snap,'restore_source')
        self.assertEqual(len(self.invoke('source','list','--project',pid)['data']['sources']),1)

    def test_draft_delete_preserves_history_reports_impact_and_reuses_identity(self):
        pid,source,draft,review,_=self.initial_chain();obj=draft['data']['objects'][0]
        removed=self.lifecycle(pid,'draft','delete',obj['object_id'],obj['revision_id'],'delete_draft')['data']
        self.assertTrue(removed['archived']);self.assertTrue(removed['affected_reviews'])
        self.assertEqual(self.invoke('draft','list','--project',pid)['data']['objects'],[])
        self.assertTrue(self.invoke('draft','show','--project',pid,'--object',obj['object_id'],'--revision',obj['revision_id'])['data']['items'])
        self.assertEqual(self.invoke('draft','show','--project',pid,'--object',obj['object_id'])['data']['items'],[])
        self.assertTrue(self.lifecycle(pid,'draft','delete',obj['object_id'],obj['revision_id'],'delete_draft')['meta']['replayed'])
        self.lifecycle(pid,'draft','restore',obj['object_id'],obj['revision_id'],'stale_restore',code=4)
        restored=self.lifecycle(pid,'draft','restore',obj['object_id'],removed['revision_id'],'restore')['data']
        self.assertFalse(restored['archived']);self.assertNotEqual(restored['revision_id'],removed['revision_id'])
        self.assertEqual(self.invoke('draft','list','--project',pid)['data']['objects'][0]['id'],obj['object_id'])

    def test_review_delete_requires_draft_cause_and_restore_cannot_reuse_it(self):
        pid,source,draft,review,body=self.initial_chain();obj=review['data']['documents'][0]
        prepared=self.prepare(pid,review)
        self.lifecycle(pid,'review','delete',obj['object_id'],obj['revision_id'],'invalid_cause',code=5,
                       read_basis=prepared['read_basis'],cause_change_ids=[source['meta']['change_id']])
        guide=self.guide(pid,source,review);prepared=self.prepare(pid,review)
        removed=self.lifecycle(pid,'review','delete',obj['object_id'],obj['revision_id'],'delete_review',
                               read_basis=prepared['read_basis'],cause_change_ids=[guide['meta']['change_id']])['data']
        self.assertTrue(removed['archived']);self.assertEqual(self.invoke('review','list','--project',pid)['data']['objects'],[])
        self.assertTrue(self.invoke('review','show','--project',pid,'--object',obj['object_id'],'--revision',obj['revision_id'])['data']['blocks'])
        current=self.invoke('review','show','--project',pid,'--object',obj['object_id'])['data']
        self.assertEqual(current['blocks'],[]);self.assertTrue(current['archived_at'])
        restored=self.lifecycle(pid,'review','restore',obj['object_id'],removed['revision_id'],'restore_review')['data']
        update=copy.deepcopy(body);doc=update['documents'][0]
        doc['target']['object_id']=obj['object_id'];doc['base_revision']=restored['revision_id'];doc['read_basis']=prepared['read_basis']
        doc['set_blocks'][0]['cause_change_ids']=[guide['meta']['change_id']]
        err=self.write(pid,'review.publish',update,'reuse_cause',code=5)
        self.assertEqual(err['error']['code'],'CAUSE_ALREADY_APPLIED')
        newguide=self.guide(pid,source,review,'newguide',guide['data']['objects'][0])
        doc['read_basis']=self.prepare(pid,review)['read_basis']+[{'object_id':draft['data']['objects'][0]['object_id'],'revision_id':draft['data']['objects'][0]['revision_id']}];doc['set_blocks'][0]['cause_change_ids']=[newguide['meta']['change_id']]
        self.write(pid,'review.publish',update,'rebuild')

    def test_removing_last_review_block_via_publish_archives_atomically(self):
        pid,source,draft,review,body=self.initial_chain();obj=review['data']['documents'][0]
        # The draft deletion itself is a valid cause for removing its dependent result.
        removed=self.lifecycle(pid,'draft','delete',draft['data']['objects'][0]['object_id'],draft['data']['objects'][0]['revision_id'],'delete_basis')
        doc=body['documents'][0];blocks=doc.pop('set_blocks');doc['target']['object_id']=obj['object_id'];doc['base_revision']=obj['revision_id']
        doc['read_basis']=self.prepare(pid,review)['read_basis'];doc['remove_blocks']=[{'block_id':b['block_id'],'cause_change_ids':[removed['meta']['change_id']]} for b in blocks]
        saved=self.write(pid,'review.publish',body,'remove_last')
        self.assertTrue(saved['data']['documents'][0]['archived'])
        self.assertEqual(self.invoke('review','list','--project',pid)['data']['objects'],[])
        app=App(self.data_dir)
        try:
            view=browser_view(app.db,self.data_dir,pid)
            self.assertTrue(next(o for o in view['objects'] if o['id']==obj['object_id'])['archived_at'])
            self.assertTrue(any(r['id']==obj['revision_id'] for r in view['object_revisions']))
        finally:app.close()

    def test_cross_project_wrong_layer_stale_and_unknown_fields_rejected(self):
        pid,source,draft,review,_=self.initial_chain();obj=draft['data']['objects'][0]
        other=self.project('other','另一个项目')['data']['project_id']
        self.lifecycle(other,'draft','delete',obj['object_id'],obj['revision_id'],'cross',code=5)
        self.lifecycle(pid,'draft','delete',obj['object_id'],'rev_stale','stale',code=4)
        self.lifecycle(pid,'draft','delete',review['data']['documents'][0]['object_id'],review['data']['documents'][0]['revision_id'],'layer',code=5)
        self.lifecycle(pid,'draft','delete',obj['object_id'],obj['revision_id'],'unknown',code=2,force=True)
        self.assertEqual(len(self.invoke('draft','list','--project',pid)['data']['objects']),1)


    def test_deleting_adopted_draft_requires_and_records_a_new_decision(self):
        from tests import test_draft
        from yuplus.core import YuError
        fixture=test_draft.DraftTests();fixture.setUp()
        try:
            initial,response=fixture.adopted();obj=response['data']['objects'][0]
            request={'api_version':'1','command':'draft.delete','reason':'撤销预算对象','object_id':obj['object_id'],'base_revision':obj['revision_id']}
            with self.assertRaises(YuError) as error:fixture.execute('draft.delete',request)
            self.assertEqual(error.exception.code,'DECISION_REQUIRED')
            current=fixture.app.execute('draft.show',{'object_id':obj['object_id']},project_id=fixture.pid)['data']
            self.assertIsNone(current['archived_at']);self.assertTrue(current['items'])
            decision=copy.deepcopy(initial['decisions'][0]);decision.update(decision_key='retire',statement='撤销预算对象',supersedes_id=response['data']['decisions'][0]['decision_id'])
            decision['affected_items'][0]['op_id']='delete';request['decisions']=[decision]
            removed=fixture.execute('draft.delete',request)
            self.assertTrue(removed['data']['archived']);self.assertEqual(len(removed['data']['decisions']),1)
            self.assertEqual(len(fixture.app.execute('decisions.list',{},project_id=fixture.pid)['data']['decisions']),2)
        finally:fixture.tearDown()

    def test_source_asset_delete_keeps_original_bytes_and_backup(self):
        import hashlib
        from yuplus.backup import create_backup
        pid=self.project()['data']['project_id'];local=Path(self.temp.name)/'original.pdf';content=b'%PDF-1.4 test original';local.write_bytes(content)
        body=cli_tests.example('02-source-local.input.json');body['snapshot']['assets'][0]['local_path']=str(local)
        source=self.write(pid,'source.import',body,'local')['data']
        blob=self.data_dir/'objects'/'sha256'/hashlib.sha256(content).hexdigest()[:2]/hashlib.sha256(content).hexdigest()
        self.lifecycle(pid,'source','delete',source['source_id'],source['snapshot_id'],'remove_file')
        self.assertEqual(blob.read_bytes(),content);self.assertEqual(local.read_bytes(),content)
        self.assertEqual(self.invoke('source','show','--project',pid,'--source',source['source_id'])['data']['snapshot']['assets'][0]['availability'],'available')
        backup=Path(self.temp.name)/'backup';create_backup(self.data_dir,backup)
        self.assertTrue(any(p.is_file() and p.read_bytes()==content for p in backup.rglob('*')))
        # Duplicate registration points back to the retained identity instead of losing its history.
        error=self.write(pid,'source.import',body,'duplicate',code=4);self.assertEqual(error['error']['code'],'SOURCE_DUPLICATE')

    def test_resource_object_delete_rejects_dangling_delivery_references(self):
        from tests import test_draft
        from yuplus.core import YuError
        fixture=test_draft.DraftTests();fixture.setUp()
        try:
            resource={'op_id':'resource','type_key':'resources','scope_key':'project','base_revision':None,'set_items':[{'item_id':'alice','data':{'name':'Alice'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
            delivery={'op_id':'delivery','type_key':'deliverables','scope_key':'project','base_revision':None,'set_items':[{'item_id':'video','data':{'deliverable':'视频','resource_item_id':'alice'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
            created=fixture.execute('draft.apply',fixture.request([resource,delivery]))['data']['objects'];obj=created[0]
            with self.assertRaises(YuError) as error:
                fixture.execute('draft.delete',{'api_version':'1','command':'draft.delete','object_id':obj['object_id'],'base_revision':obj['revision_id'],'reason':'删除资源'})
            self.assertEqual(error.exception.code,'INVALID_ITEM_REFERENCE')
            current=fixture.app.execute('draft.show',{'object_id':obj['object_id']},project_id=fixture.pid)['data']
            self.assertIsNone(current['archived_at']);self.assertEqual(current['revision_id'],obj['revision_id'])
        finally:fixture.tearDown()


# Keep this suite focused on the added cases; inherited methods remain covered by test_cli.
for name in dir(cli_tests.CliAcceptanceTests):
    if name.startswith('test_') and name not in LifecycleTests.__dict__:
        setattr(LifecycleTests,name,None)
