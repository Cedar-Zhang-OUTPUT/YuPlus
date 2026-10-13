import copy
import tempfile
import unittest
from pathlib import Path
from yuplus.app import App
from yuplus.core import YuError

class DraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=App(Path(self.tmp.name));self.n=0
        self.pid=self.app.execute('project.create',{'name':'城市展'},request_id='project')['data']['project_id']
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def execute(self,cmd,payload):
        self.n+=1
        return self.app.execute(cmd,payload,project_id=self.pid,request_id='r_'+str(self.n))
    def request(self,ops,decisions=None):return {'api_version':'1','command':'draft.apply','reason':'整理信息','objects':ops,'decisions':decisions or []}
    def item(self,key='budget',amount='100000000'):
        return {'item_id':key,'data':{'currency':'CNY','max_minor':amount},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}
    def op(self,items=None,**kw):
        return {'op_id':'budget','type_key':'budget_range','scope_key':'project','base_revision':None,'set_items':items or [self.item()],**kw}
    def make(self):return self.execute('draft.apply',self.request([self.op()]))['data']['objects'][0]
    def test_incomplete_hypothesis_is_valid_and_repeated_edit_is_noop(self):
        first=self.make()
        op=self.op(object_id=first['object_id'],base_revision=first['revision_id'])
        second=self.execute('draft.apply',self.request([op]))
        self.assertEqual(second['data']['effect'],'noop')
        self.assertEqual(second['data']['objects'][0]['revision_id'],first['revision_id'])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM object_revisions').fetchone()[0],1)
    def test_changed_item_preserves_siblings_and_old_version(self):
        first=self.execute('draft.apply',self.request([self.op(items=[self.item(),self.item('contingency','1000000')])]))['data']['objects'][0]
        op=self.op(object_id=first['object_id'],base_revision=first['revision_id'],items=[self.item(amount='60000000')])
        second=self.execute('draft.apply',self.request([op]))['data']['objects'][0]
        latest=self.app.execute('draft.show',{'object_id':first['object_id']},project_id=self.pid)['data']
        historical=self.app.execute('draft.show',{'object_id':first['object_id'],'revision_id':first['revision_id']},project_id=self.pid)['data']
        self.assertEqual(latest['items'][0]['data']['max_minor'],'60000000');self.assertEqual(len(latest['items']),2)
        self.assertEqual(historical['items'][0]['data']['max_minor'],'100000000');self.assertEqual(second['version'],2)
    def test_stale_base_rolls_back_whole_batch(self):
        first=self.make()
        other={'op_id':'brand','type_key':'brand_assets','scope_key':'project','base_revision':None,'set_items':[{'item_id':'logo','data':{'topic':'标识'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
        stale=self.op(object_id=first['object_id'],base_revision=None)
        with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([other,stale]))
        self.assertEqual(error.exception.code,'BASE_REVISION_CONFLICT')
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM objects').fetchone()[0],1)
    def test_money_range_and_currency_are_checked(self):
        for data in ({'min_minor':'20','max_minor':'10','currency':'CNY'},{'max_minor':'10'}):
            item=self.item();item['data']=data
            with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([self.op([item])]))
            self.assertEqual(error.exception.code,'INVALID_MONEY')
    def test_facts_require_sources(self):
        item=self.item();item['epistemic_kind']='source_statement'
        with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([self.op([item])]))
        self.assertEqual(error.exception.code,'SOURCE_EVIDENCE_REQUIRED')
    def test_adopted_value_requires_decision(self):
        item=self.item();item['epistemic_kind']='adopted_decision'
        with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([self.op([item])]))
        self.assertEqual(error.exception.code,'DECISION_REQUIRED')
    def test_duplicate_and_overlapping_item_ids_rejected(self):
        for op in [self.op([self.item(),self.item()]),self.op(remove_items=['budget'])]:
            with self.assertRaises(YuError):self.execute('draft.apply',self.request([op]))
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM objects').fetchone()[0],0)
    def test_item_order_must_be_complete_permutation(self):
        with self.assertRaises(YuError):self.execute('draft.apply',self.request([self.op(item_order=[])]))
    def test_same_batch_dependencies_resolve_and_cycles_reject(self):
        second={'op_id':'assessment','type_key':'project_assessment','scope_key':'project','base_revision':None,'set_items':[{'item_id':'investment','data':{'finding':'投入估算'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[{'dependency_id':'dep','op_id':'budget','item_id':'budget','kind':'derivation'}]}]}
        result=self.execute('draft.apply',self.request([second,self.op()]))
        self.assertEqual(len(result['data']['objects']),2)
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM revision_dependencies').fetchone()[0],1)
        # New project isolates creation cycle from existing objects.
        self.pid=self.app.execute('project.create',{'name':'cycle'},request_id='project_cycle')['data']['project_id']
        first=self.op();first['set_items'][0]['dependencies']=[{'dependency_id':'dep','op_id':'assessment','item_id':'investment','kind':'derivation'}]
        with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([first,second]))
        self.assertEqual(error.exception.code,'DEPENDENCY_CYCLE')
    def test_cross_project_object_cannot_be_modified(self):
        first=self.make();self.pid=self.app.execute('project.create',{'name':'other'},request_id='other')['data']['project_id']
        with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([self.op(object_id=first['object_id'],base_revision=first['revision_id'])]))
        self.assertEqual(error.exception.code,'CROSS_PROJECT_REFERENCE')
    def test_invalid_calendar_date_is_rejected(self):
        op={'op_id':'date','type_key':'milestones','scope_key':'project','base_revision':None,'set_items':[{'item_id':'launch','data':{'event':'启动','time_kind':'date','start':'2026-02-31'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
        with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([op]))
        self.assertEqual(error.exception.code,'INVALID_TIME')
    def test_expression_guide_requires_real_review_target(self):
        op={'op_id':'guide','type_key':'expression_guide','scope_key':'review:missing','base_revision':None,'set_items':[{'item_id':'shorter','data':{'review_object_id':'missing','block_ids':['*'],'instruction':'写短些','intent':'rewrite'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
        with self.assertRaises(YuError):self.execute('draft.apply',self.request([op]))
    def adopted(self,count=1):
        source={'api_version':'1','command':'source.import','target':{'mode':'create','provider':'oral','resource_type':'statement'},'snapshot':{'title':'用户决定','provider_revision':None,'captured_at':'2026-10-13T02:00:00Z','capture_scope':{'kind':'whole_resource'},'extraction_profile':'text-v1','body':{'format':'text','text':'采用预算方案'},'provenance':{'method':'conversation-verbatim'}},'advance_head':True,'reason':'记录决定原话'}
        sid=self.execute('source.import',source)['data']['snapshot_id'];items=[];decisions=[]
        for n in range(count):
            item=self.item(key='budget_'+str(n));item.update(epistemic_kind='adopted_decision',source_refs=[{'evidence_id':'instruction','source_version_id':sid,'kind':'instruction'}]);items.append(item)
            decisions.append({'decision_key':'d_'+str(n),'statement':'采用预算'+str(n),'decided_by':'主策','instruction_source_version_id':sid,'rationale':'按原话','affected_items':[{'op_id':'budget','item_id':item['item_id']}]})
        request=self.request([self.op(items)],decisions);response=self.execute('draft.apply',request)
        return request,response
    def test_adopted_kind_cannot_be_downgraded_to_bypass_decision(self):
        request,first=self.adopted();obj=first['data']['objects'][0]
        op=request['objects'][0];op.update(object_id=obj['object_id'],base_revision=obj['revision_id']);op['set_items'][0]['epistemic_kind']='hypothesis';op['set_items'][0]['data']['max_minor']='1';request['decisions']=[]
        with self.assertRaises(YuError) as error:self.execute('draft.apply',request)
        self.assertEqual(error.exception.code,'DECISION_REQUIRED')
    def test_removing_adopted_item_requires_decision(self):
        request,first=self.adopted();obj=first['data']['objects'][0]
        op=request['objects'][0];op.update(object_id=obj['object_id'],base_revision=obj['revision_id'],remove_items=['budget_0']);op.pop('set_items');request['decisions']=[]
        with self.assertRaises(YuError) as error:self.execute('draft.apply',request)
        self.assertEqual(error.exception.code,'DECISION_REQUIRED')
    def test_unchanged_adoption_is_noop_without_new_decision(self):
        request,first=self.adopted();obj=first['data']['objects'][0]
        request['objects'][0].update(object_id=obj['object_id'],base_revision=obj['revision_id'])
        result=self.execute('draft.apply',request)
        self.assertEqual(result['data']['effect'],'noop');self.assertEqual(result['data']['decisions'],[])
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM decisions').fetchone()[0],1)
    def test_decision_pagination_retains_same_batch_records_and_scopes_cursor(self):
        self.adopted(count=3)
        first=self.app.execute('decisions.list',{'limit':1},project_id=self.pid)['data'];seen=[first['decisions'][0]['id']];cursor=first['next_cursor']
        while cursor is not None:
            page=self.app.execute('decisions.list',{'limit':1,'after_cursor':cursor},project_id=self.pid)['data']
            seen.extend(d['id'] for d in page['decisions']);cursor=page['next_cursor']
        self.assertEqual(len(set(seen)),3)
        other=self.app.execute('project.create',{'name':'other'},request_id='other')['data']['project_id']
        with self.assertRaises(YuError):self.app.execute('decisions.list',{'after_cursor':first['next_cursor']},project_id=other)
        with self.assertRaises(YuError):self.app.execute('changes.list',{'after_cursor':first['next_cursor']},project_id=self.pid)
    def test_resource_removal_cannot_leave_typed_reference_dangling(self):
        resource={'op_id':'resource','type_key':'resources','scope_key':'project','base_revision':None,'set_items':[{'item_id':'alice','data':{'name':'Alice'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
        delivery={'op_id':'delivery','type_key':'deliverables','scope_key':'project','base_revision':None,'set_items':[{'item_id':'video','data':{'deliverable':'视频','resource_item_id':'alice'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
        result=self.execute('draft.apply',self.request([resource,delivery]));obj=result['data']['objects'][0]
        removal={k:v for k,v in resource.items() if k!='set_items'};removal.update(object_id=obj['object_id'],base_revision=obj['revision_id'],remove_items=['alice'])
        with self.assertRaises(YuError) as error:self.execute('draft.apply',self.request([removal]))
        self.assertEqual(error.exception.code,'INVALID_ITEM_REFERENCE')
        self.assertEqual(self.app.execute('draft.show',{'object_id':obj['object_id']},project_id=self.pid)['data']['items'][0]['item_id'],'alice')
