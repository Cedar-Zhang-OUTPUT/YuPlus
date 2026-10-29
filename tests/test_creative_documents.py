import copy
import unittest
from tests import test_draft
from yuplus.core import YuError,load_revision
from yuplus.collaboration import OUTLINES

class CreativeDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.fx=test_draft.DraftTests();self.fx.setUp();self.addCleanup(self.fx.tearDown)
    def save(self,typ,data,previous=None,item_id='one'):
        op={'op_id':'object','type_key':typ,'scope_key':'project','base_revision':previous['revision_id'] if previous else None,'set_items':[{'item_id':item_id,'data':data,'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
        if previous:op['object_id']=previous['object_id']
        return self.fx.execute('draft.apply',self.fx.request([op]))['data']['objects'][0]
    def document(self,proposal):
        dep={'dependency_id':'p','object_id':proposal['object_id'],'revision_id':proposal['revision_id'],'item_id':'one','kind':'fact'}
        return {'api_version':'1','command':'review.publish','reason':'整理创意方案','documents':[{'target':{'type_key':'creative_plan','scope_key':'proposal:one'},'base_revision':None,'outline_version':2,'read_basis':[{'object_id':proposal['object_id'],'revision_id':proposal['revision_id']}],'structure_cause_change_ids':[],'set_blocks':[{'block_id':'body','markdown':'\n\n'.join('## '+h+'\n\n已有方向，细节待讨论。' for h in OUTLINES['creative_plan']),'dependencies':[dep],'cause_change_ids':[]}]}]}
    def test_specific_proposal_scope_and_fixed_outline(self):
        p=self.save('creative_proposals',{'title':'江线','concept':'从人的生活理解城市','development':{'zones':'三个生活场景'}})
        body=self.document(p);saved=self.fx.execute('review.publish',body)['data']['documents'][0]
        self.assertEqual(load_revision(self.fx.app.db,self.fx.pid,saved['revision_id'])['payload']['outline_version'],2)
        broken=copy.deepcopy(body);broken['documents'][0]['target']['scope_key']='proposal:unknown'
        with self.assertRaises(YuError):self.fx.execute('review.publish',broken)
        # A second real direction still cannot author arbitrary headings.
        p2=self.save('creative_proposals',{'title':'另一方向'},p,item_id='two');broken=self.document(p2)
        doc=broken['documents'][0];doc['target']['scope_key']='proposal:two';doc['set_blocks'][0]['dependencies'][0]['item_id']='two';doc['set_blocks'][0]['markdown']='## 任意结构\n\n不能这样写'
        with self.assertRaises(YuError):self.fx.execute('review.publish',broken)
    def test_feedback_retains_exact_historical_target(self):
        p=self.save('creative_proposals',{'title':'江线','concept':'初版'})
        target={'dependency_id':'feedback_target','object_id':p['object_id'],'revision_id':p['revision_id'],'item_id':'one','kind':'fact'}
        feedback=self.save('creative_feedback',{'feedback':'补入口的人的声音','reviewer':'同事 A','target':target,'nature':'suggestion'})
        self.save('creative_proposals',{'title':'江线','concept':'加入入口人声'},p)
        data=load_revision(self.fx.app.db,self.fx.pid,feedback['revision_id'])['payload']['items'][0]['data']
        self.assertEqual(data['target']['revision_id'],p['revision_id'])
        with self.assertRaises(YuError):self.save('creative_feedback',{'target':{**target,'item_id':'missing'},'feedback':'无目标'},feedback)
    def test_task_references_and_adoption_are_validated(self):
        with self.assertRaises(YuError):self.save('creative_proposals',{'title':'江线','task_item_ids':['missing']})
        with self.assertRaises(YuError):self.save('creative_proposals',{'title':'江线','adoption':'adopted'})
        with self.assertRaises(YuError):self.save('creative_feedback',{'feedback':'已定','nature':'confirmed_decision'})
