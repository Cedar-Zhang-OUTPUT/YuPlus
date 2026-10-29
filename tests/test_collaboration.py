"""Collaboration races and provenance tested on real SQLite; only Feishu is faked."""
import copy
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from yuplus.app import App
from yuplus.core import YuError,canonical
from yuplus import collaboration as c

class Remote:
    def __init__(self):self.snapshot={'revision':1,'content':'','reference_map':{}};self.writes=0;self.serial=0;self.race=None
    def fetch(self,url):return copy.deepcopy(self.snapshot)
    def identify(self,xml):
        root=ET.fromstring('<root>'+xml+'</root>')
        for n in root:
            self.serial+=1;n.set('id','block'+str(self.serial))
        return ''.join(ET.tostring(n,encoding='unicode') for n in root if n.tag!='title')
    def write(self,args,xml):
        self.writes+=1
        if '+create' in args:self.snapshot['content']=self.identify(xml)
        else:
            revision=int(args[args.index('--revision-id')+1])
            if self.race:self.race(self);self.race=None
            if revision!=self.snapshot['revision']:raise YuError('FEISHU_UNAVAILABLE','revision conflict')
            if 'append' in args:self.snapshot['content']+=self.identify(xml)
            else:
                start=args[args.index('--start-block-id')+1];end=args[args.index('--end-block-id')+1]
                ns=c.nodes(self.snapshot);a=next(i for i,n in enumerate(ns) if n.get('id')==start);b=next(i for i,n in enumerate(ns) if n.get('id')==end)
                self.snapshot['content']=''.join(ET.tostring(n,encoding='unicode') for n in ns[:a])+self.identify(xml)+''.join(ET.tostring(n,encoding='unicode') for n in ns[b+1:])
        self.snapshot['revision']+=1
        return {'document':{'url':'https://example.feishu.cn/docx/testDocument'}}
    def edit(self,old,new):self.snapshot['content']=self.snapshot['content'].replace(old,new);self.snapshot['revision']+=1

class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=App(Path(self.tmp.name)/'data');self.addCleanup(self.app.close)
        self.pid=self.app.execute('project.create',{'name':'协作测试'},request_id='project')['data']['project_id'];self.n=0
        self.remote=Remote()
        self.addCleanup(patch.stopall)
        patch('yuplus.collaboration.fetch',self.remote.fetch).start();patch('yuplus.collaboration.remote_write',self.remote.write).start()
        self.draft=None;self.review=None
        self.update('100');self.publish('100')
    def runcommand(self,cmd,p=None,key=None):
        self.n+=1
        return self.app.execute(cmd,p or {},project_id=self.pid,request_id=key or 'r'+str(self.n))
    def update(self,amount,source=None):
        item={'item_id':'budget','data':{'max_minor':amount,'currency':'CNY'},'epistemic_kind':'source_statement' if source else 'hypothesis','source_refs':[{'evidence_id':'remote','source_version_id':source,'kind':'supports'}] if source else [],'dependencies':[]}
        op={'op_id':'b','type_key':'budget_range','scope_key':'project','base_revision':self.draft['revision_id'] if self.draft else None,'set_items':[item]}
        if self.draft:op['object_id']=self.draft['object_id']
        result=self.runcommand('draft.apply',{'api_version':'1','command':'draft.apply','reason':'调整预算','objects':[op],'decisions':[]})
        self.draft=result['data']['objects'][0];self.cause=result['meta']['change_id'];return result
    def publish(self,text,cause=True):
        dep={'dependency_id':'basis','object_id':self.draft['object_id'],'revision_id':self.draft['revision_id'],'item_id':'budget','kind':'fact'}
        doc={'target':{'type_key':'debrief','scope_key':'project'},'base_revision':self.review['revision_id'] if self.review else None,'read_basis':[{'object_id':self.draft['object_id'],'revision_id':self.draft['revision_id']}],'structure_cause_change_ids':[],'set_blocks':[{'block_id':'budget','markdown':text,'dependencies':[dep],'cause_change_ids':[self.cause] if self.review and cause else []}]}
        if self.review:doc['target']['object_id']=self.review['object_id']
        result=self.runcommand('review.publish',{'api_version':'1','command':'review.publish','reason':'更新成果','documents':[doc]});self.review=result['data']['documents'][0];self.key=self.review['object_id']+':budget';return result
    def create(self):return self.runcommand('collab.create',{'sections':{self.key:'<p>100</p>'}},'create')
    def pull(self):return self.runcommand('collab.pull')['data']
    def code(self,expected,fn):
        with self.assertRaises(YuError) as caught:fn()
        self.assertEqual(caught.exception.code,expected)
    def test_malformed_payloads_fail_before_remote_write(self):
        for payload in ({'key':[],'xml':'<p>x</p>','base_revision':1,'expected_local_revision':'r'},
                        {'key':'k','xml':'<p>x</p>','base_revision':True,'expected_local_revision':'r'},
                        {'key':'k'}):
            self.code('INVALID_INPUT',lambda:self.runcommand('collab.push',payload))
        self.code('INVALID_INPUT',lambda:self.runcommand('collab.step',{'event_id':'e','command':'draft.apply','input':[]}))
        self.assertEqual(self.remote.writes,0)
    def test_create_warning_retains_locator_and_prevents_duplicate(self):
        original=self.remote.write
        def warning(args,xml):return original(args,xml)|{'warnings':['media not rendered']}
        with patch('yuplus.collaboration.remote_write',warning):
            self.code('COLLAB_WRITE_UNCERTAIN',self.create)
        self.assertTrue(self.runcommand('collab.show')['data']['binding']['url'])
        self.code('COLLAB_WRITE_UNCERTAIN',self.create)
        self.assertEqual(self.remote.writes,1)
    def test_create_replay_and_no_false_inbox(self):
        first=self.create();second=self.create();self.assertEqual(self.remote.writes,1);self.assertTrue(second['meta']['replayed'])
        self.assertEqual(first['data']['url'],second['data']['url']);self.assertEqual(self.pull()['events'],[])
    def test_remote_is_deduplicated_and_requires_draft_then_review(self):
        self.create();self.remote.edit('100','60');data=self.pull();event=data['events'][-1]
        self.assertEqual(data['classification'][self.key],'remote');self.assertTrue(event['source_snapshot_id'])
        self.assertEqual(self.pull()['events'][-1]['source_snapshot_id'],event['source_snapshot_id'])
        self.code('DRAFT_CHANGE_REQUIRED',lambda:self.publish('60',False))
        accept={'event_id':event['id'],'outcome':'applied','reason':'吸收团队预算补充','change_ids':[],'handled_keys':[self.key]}
        self.code('DRAFT_CHANGE_REQUIRED',lambda:self.runcommand('collab.accept',accept))
        changed=self.update('60',event['source_snapshot_id']);accept['change_ids']=[changed['meta']['change_id']]
        self.code('COLLAB_REVIEW_PENDING',lambda:self.runcommand('collab.accept',accept))
        self.publish('60');done=self.runcommand('collab.accept',accept)['data']
        self.assertEqual(done['pending'],0);self.assertFalse(done['local_pending'])
    def test_same_section_conflict_requires_instruction(self):
        self.create();self.update('80');self.publish('80');self.remote.edit('100','60');data=self.pull()
        self.assertEqual(data['classification'][self.key],'conflict');self.assertEqual(data['events'][-1]['state'],'conflict')
        self.code('COLLAB_CONFLICT',lambda:self.runcommand('collab.push',{'key':self.key,'xml':'<p>80</p>','base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']}))
        self.code('INVALID_INPUT',lambda:self.runcommand('collab.resolve',{'event_id':data['events'][-1]['id'],'choice':'local','reason':'随便','instruction_source_version_id':'fake'}))
    def test_local_push_checks_both_versions_and_no_self_echo(self):
        self.create();self.update('80');self.publish('80');data=self.pull()
        body={'key':self.key,'xml':'<p>80</p>','base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']}
        self.code('BASE_REVISION_CONFLICT',lambda:self.runcommand('collab.push',{**body,'expected_local_revision':'old'}))
        self.code('COLLAB_REMOTE_CHANGED',lambda:self.runcommand('collab.push',{**body,'base_revision':0}))
        result=self.runcommand('collab.push',body);self.assertFalse(result['data']['local_pending']);self.assertEqual(self.pull()['events'],[])
        self.assertIn('80',self.remote.snapshot['content'])
    def test_race_at_write_cannot_overwrite_team_edit(self):
        self.create();self.update('80');self.publish('80');data=self.pull()
        self.remote.race=lambda remote:remote.edit('100','65')
        body={'key':self.key,'xml':'<p>80</p>','base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']}
        self.code('FEISHU_UNAVAILABLE',lambda:self.runcommand('collab.push',body,'race'))
        self.code('COLLAB_WRITE_UNCERTAIN',lambda:self.runcommand('collab.push',body,'race'))
        self.assertIn('65',self.remote.snapshot['content']);self.assertNotIn('80',self.remote.snapshot['content'])
    def test_accept_rechecks_remote_and_does_not_ack_unread_edit(self):
        self.create();self.remote.snapshot['reference_map']={'comments':['first']};self.remote.snapshot['revision']+=1;data=self.pull();event=data['events'][-1]
        self.remote.snapshot['reference_map']={'comments':['second']};self.remote.snapshot['revision']+=1
        self.code('COLLAB_REMOTE_CHANGED',lambda:self.runcommand('collab.accept',{'event_id':event['id'],'outcome':'no_business_change','reason':'旧评论无业务变化','handled_keys':[]}))
        self.assertEqual(len(self.pull()['events']),2)
    def test_three_way_different_sections_and_deletions(self):
        base={'local':{'a':{'hash':'one'},'b':{'hash':'two'}},'remote':{'a':{'hash':'ONE'},'b':{'hash':'TWO'}}}
        self.assertEqual(c.changes(base,{'a':{'hash':'changed'},'b':{'hash':'two'}},{'a':{'hash':'ONE'},'b':{'hash':'team'}}),{'a':'local','b':'remote'})
        self.assertEqual(c.changes(base,base['local'],{'a':None,'b':{'hash':'TWO'}})['a'],'remote')
    def test_mapping_and_xml_validation(self):
        self.code('INVALID_INPUT',lambda:self.runcommand('collab.create',{'sections':{self.key:5}}))
        self.code('INVALID_INPUT',lambda:self.runcommand('collab.create',{'sections':{self.key:'<title>wrong</title>'}}))
        self.assertEqual(self.remote.writes,0)
    def test_no_business_change_cannot_ignore_body_change(self):
        self.create();self.remote.edit('100','50');d=self.pull();e=d['events'][-1]
        self.code('DRAFT_CHANGE_REQUIRED',lambda:self.runcommand('collab.accept',{'event_id':e['id'],'outcome':'no_business_change','reason':'忽略','handled_keys':[self.key]}))
    def test_catalog_codes_contiguous_and_ids_stable(self):
        catalog=self.app.execute('types.show')['data']['objects']
        self.assertEqual([o['code'] for o in catalog],[f'D{i:02}' for i in range(1,26)])
        oldid=self.draft['object_id'];self.update('70');self.assertEqual(self.draft['object_id'],oldid)

    def test_resolved_merge_stays_pending_until_remote_push(self):
        self.create();self.update('80');self.publish('80');self.remote.edit('100','60');d=self.pull();e=d['events'][-1]
        from tests.test_cli import example
        source=example('03-source-oral.input.json');source['snapshot']['body']['text']='用户确认综合两方，按 70 处理。'
        instruction=self.runcommand('source.import',source)['data']['snapshot_id']
        self.runcommand('collab.resolve',{'event_id':e['id'],'instruction_source_version_id':instruction,'choice':'merge','reason':'用户确认按70合并'})
        changed=self.update('70',e['source_snapshot_id']);self.publish('70')
        done=self.runcommand('collab.accept',{'event_id':e['id'],'outcome':'applied','reason':'已按选择整理双方信息','handled_keys':[self.key],'change_ids':[changed['meta']['change_id']]})['data']
        self.assertTrue(done['local_pending']);d=self.pull();self.assertEqual(d['classification'][self.key],'local')
        self.runcommand('collab.push',{'key':self.key,'xml':'<p>70</p>','base_revision':d['remote_revision'],'expected_local_revision':self.review['revision_id']})
        self.assertIn('70',self.remote.snapshot['content']);self.assertFalse(self.runcommand('collab.show')['data']['binding']['local_pending'])

    def test_project_lock_prevents_concurrent_business_write(self):
        with c.lock(self.app,self.pid):
            self.code('PROJECT_BUSY',lambda:self.update('50'))
        self.update('50')

    def test_backup_restore_pauses_collaboration_and_clears_scheduler(self):
        from yuplus.backup import create_backup,restore_backup
        self.create();self.runcommand('collab.scheduler-bind',{'schedule':{'automation_id':'actual_test_task','thread_id':'test_thread','host_id':'local','interval_minutes':5,'state':'active'}})
        backup=Path(self.tmp.name)/'backup';restored=Path(self.tmp.name)/'restored'
        create_backup(self.app.data_dir,backup);restore_backup(backup,restored)
        app=App(restored)
        try:
            binding=c.public(app.db,self.pid);self.assertFalse(binding['enabled']);self.assertEqual(binding['schedule'],{})
            self.assertEqual(binding['url'],c.public(self.app.db,self.pid)['url'])
        finally:app.close()

    def authored_create(self,xml=None,mappings=None):
        local=c.local_sections(self.app.db,self.pid)
        return self.runcommand('collab.create',{'xml':xml or '<title>项目策划</title><h1>主策 Debrief</h1><h2>项目任务</h2><p>100</p>',
            'mappings':mappings or {self.key:{'start':1,'end':2}},
            'expected_local_revisions':{k:v['revision_id'] for k,v in local.items()}})

    def add_qa(self,answers=('待答复','待答复'),source=None):
        items=[{'item_id':'q'+str(i),'data':{'question':q,'answer':a,'asked_by':'主策','answered_by':'客户'},
                'epistemic_kind':'source_statement' if source else 'hypothesis',
                'source_refs':[{'evidence_id':'remote','source_version_id':source,'kind':'supports'}] if source else [],'dependencies':[]}
               for i,(q,a) in enumerate(zip(('是否确认档期？','是否确认场地？'),answers))]
        current=getattr(self,'qa',None)
        op={'op_id':'qa','type_key':'qa','scope_key':'project','base_revision':current['revision_id'] if current else None,'set_items':items}
        if current:op['object_id']=current['object_id']
        result=self.runcommand('draft.apply',{'api_version':'1','command':'draft.apply','reason':'整理客户澄清','objects':[op],'decisions':[]})
        self.qa=result['data']['objects'][0];self.qa_keys=[self.qa['object_id']+':q'+str(i) for i in range(2)]
        return result

    def grouped_create(self):
        self.add_qa()
        xml='<title>项目策划</title><h1>主策 Debrief</h1><p>100</p><h1>客户 Q&amp;A</h1><table><tr><td>档期：待答复</td><td>场地：待答复</td></tr></table>'
        mappings={self.key:{'start':1,'end':1},**{k:{'start':3,'end':3} for k in self.qa_keys}}
        return self.authored_create(xml,mappings)

    def test_agent_outline_survives_create_and_range_push(self):
        # Real fetch responses include the document title; it must not shift body indexes.
        identify=self.remote.identify
        self.remote.identify=lambda xml: '<title id="document">项目策划</title>'+identify(xml) if '<title>' in xml else identify(xml)
        self.authored_create();snapshot=self.remote.snapshot['content']
        self.assertEqual(snapshot.count('<h1 '),1);self.assertNotIn(' · ',snapshot)
        data=self.pull();self.assertEqual(c.nodes({'content':data['remote'][self.key]['xml']})[0].tag,'h2')
        self.update('80');self.publish('80');data=self.pull()
        self.runcommand('collab.push',{'key':self.key,'xml':'<h2>项目任务</h2><p>80</p>',
            'base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']})
        self.assertEqual(self.remote.snapshot['content'].count('<h1 '),1)
        self.assertEqual(self.pull()['events'],[])

    def test_create_checks_all_local_versions_before_writing(self):
        self.code('BASE_REVISION_CONFLICT',lambda:self.runcommand('collab.create',{'xml':'<p>100</p>',
            'mappings':{self.key:{'start':0,'end':0}},'expected_local_revisions':{self.key:'old'}}))
        self.assertEqual(self.remote.writes,0)

    def test_malformed_group_versions_return_contract_error(self):
        self.authored_create();data=self.pull()
        for expected in (None,[],{self.key:False}):
            self.code('INVALID_INPUT',lambda:self.runcommand('collab.push',{'key':self.key,'xml':'<p>100</p>',
                'base_revision':data['remote_revision'],'expected_local_revisions':expected}))
        self.assertEqual(self.remote.writes,1)

    def test_create_transformed_blocks_preserves_locator_without_guessing(self):
        original=self.remote.write
        def transform(args,xml):
            result=original(args,xml);self.remote.snapshot['content']+='<p id="extra">团队补充</p>';return result
        with patch('yuplus.collaboration.remote_write',transform):
            self.code('COLLAB_WRITE_UNCERTAIN',self.authored_create)
        binding=self.runcommand('collab.show')['data']['binding']
        self.assertTrue(binding['url']);self.assertIsNone(binding['last_synced_at'])
        self.assertTrue(binding['local_pending'])
        self.authored_create();self.assertEqual(self.remote.writes,1)

    def test_shared_qa_table_checks_and_updates_every_local_key(self):
        self.grouped_create();self.add_qa(('已确认','已确认'));data=self.pull()
        request={'key':self.qa_keys[0],'xml':'<table><tr><td>档期：已确认</td><td>场地：已确认</td></tr></table>',
            'base_revision':data['remote_revision'],'expected_local_revision':self.qa['revision_id']}
        self.code('INVALID_INPUT',lambda:self.runcommand('collab.push',request))
        request.pop('expected_local_revision');request['expected_local_revisions']={k:self.qa['revision_id'] for k in self.qa_keys}
        self.runcommand('collab.push',request)
        data=self.pull();self.assertTrue(all(v=='same' for v in data['classification'].values()))
        self.assertEqual(data['remote'][self.qa_keys[0]],data['remote'][self.qa_keys[1]])
        self.assertEqual(self.remote.snapshot['content'].count('<h1 '),2)

    def test_shared_qa_remote_edits_return_through_draft(self):
        self.grouped_create();self.remote.edit('档期：待答复','档期：已确认');data=self.pull();event=data['events'][-1]
        self.assertEqual({data['classification'][k] for k in self.qa_keys},{'remote'})
        changed=self.add_qa(('已确认','待答复'),event['source_snapshot_id'])
        accept={'event_id':event['id'],'outcome':'applied','reason':'吸收客户确认','change_ids':[changed['meta']['change_id']],'handled_keys':self.qa_keys}
        self.code('INVALID_INPUT',lambda:self.runcommand('collab.accept',{**accept,'handled_keys':self.qa_keys[:1]}))
        self.runcommand('collab.accept',accept)
        self.assertEqual(self.pull()['events'],[])
        self.assertFalse(self.runcommand('collab.show')['data']['binding']['local_pending'])

    def test_ranges_reject_partial_overlap_nested_or_missing_endpoints(self):
        self.add_qa();local=c.local_sections(self.app.db,self.pid)
        snapshot={'content':'<h1 id="a">客户 Q&amp;A</h1><p id="b">问题</p><table id="c"><tr><td id="nested">回答</td></tr></table>'}
        for mappings in ({self.qa_keys[0]:{'start':'a','end':'b'},self.qa_keys[1]:{'start':'b','end':'c'}},
                         {self.key:{'start':'c','end':'a'}},{self.key:{'start':'nested','end':'nested'}},
                         {self.key:{'start':'b','end':'gone'}}):
            self.code('INVALID_INPUT',lambda:c.validate_mappings(snapshot,mappings,local))
        shared={k:{'start':'c','end':'c'} for k in self.qa_keys}
        self.assertEqual(set(c.validate_mappings(snapshot,shared,local)),set(self.qa_keys))

    def test_bind_agent_created_document_uses_real_blocks_and_is_not_synced(self):
        self.remote.snapshot['content']='<h1 id="a">主策 Debrief</h1><p id="b">团队修改为60</p>'
        mappings={self.key:{'start':'b','end':'b'}}
        self.code('COLLAB_REMOTE_CHANGED',lambda:self.runcommand('collab.bind',{'url':'https://example.feishu.cn/docx/testDocument','mappings':mappings,'base_revision':0}))
        self.runcommand('collab.bind',{'url':'https://example.feishu.cn/docx/testDocument','mappings':mappings,'base_revision':1})
        data=self.pull();self.assertEqual(data['classification'][self.key],'remote')
        self.assertTrue(data['events'][-1]['source_snapshot_id'])
        self.assertIsNone(self.runcommand('collab.show')['data']['binding']['last_synced_at'])

    def test_remapping_unchanged_document_still_enters_inbox(self):
        self.authored_create();data=self.pull();old=data['mappings'][self.key]
        self.code('COLLAB_REMOTE_CHANGED',lambda:self.runcommand('collab.map',{'mappings':{self.key:{'start':old['end'],'end':old['end']}},'base_revision':0}))
        self.runcommand('collab.map',{'mappings':{self.key:{'start':old['end'],'end':old['end']}},'base_revision':data['remote_revision']})
        data=self.pull();self.assertEqual(data['classification'][self.key],'remote');self.assertTrue(data['events'])

    def test_legacy_heading_mapping_remains_writable(self):
        self.remote.snapshot['content']='<h1 id="a">旧标题 · 1</h1><p id="b">100</p>'
        self.runcommand('collab.bind',{'url':'https://example.feishu.cn/docx/testDocument','mappings':{self.key:'a'}})
        data=self.pull();event=data['events'][-1]
        changed=self.update('100',event['source_snapshot_id']);self.publish('100')
        self.runcommand('collab.accept',{'event_id':event['id'],'outcome':'applied','reason':'确认原始内容','change_ids':[changed['meta']['change_id']],'handled_keys':[self.key]})
        self.update('80');self.publish('80');data=self.pull()
        self.runcommand('collab.push',{'key':self.key,'xml':'<p>80</p>','base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']})
        self.assertIn('旧标题 · 1',self.remote.snapshot['content']);self.assertIn('80',self.remote.snapshot['content'])

    def test_range_push_does_not_erase_unmapped_neighbor(self):
        self.authored_create();self.remote.snapshot['content']+='<p id="team">团队自由补充</p>';self.remote.snapshot['revision']+=1
        self.update('80');self.publish('80');data=self.pull()
        self.runcommand('collab.push',{'key':self.key,'xml':'<h2>项目任务</h2><p>80</p>','base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']})
        self.assertIn('团队自由补充',self.remote.snapshot['content'])
        self.assertTrue(self.pull()['events'])

    def test_shared_table_conflict_blocks_every_member(self):
        self.grouped_create();self.add_qa(('本地档期','待答复'))
        self.remote.edit('场地：待答复','场地：远端确认');data=self.pull()
        self.assertEqual(data['classification'][self.qa_keys[0]],'conflict')
        self.code('COLLAB_CONFLICT',lambda:self.runcommand('collab.push',{'key':self.qa_keys[1],
            'xml':'<p>本地整理</p>','base_revision':data['remote_revision'],
            'expected_local_revisions':{k:self.qa['revision_id'] for k in self.qa_keys}}))
        self.assertIn('场地：远端确认',self.remote.snapshot['content']);self.assertEqual(self.remote.writes,1)

    def test_removed_range_endpoint_requires_reconciliation(self):
        self.authored_create();data=self.pull();end=data['mappings'][self.key]['end']
        self.remote.snapshot['content']=''.join(ET.tostring(n,encoding='unicode') for n in c.nodes(self.remote.snapshot) if n.get('id')!=end)
        self.remote.snapshot['revision']+=1;data=self.pull()
        self.code('COLLAB_MAPPING_REQUIRED',lambda:self.runcommand('collab.push',{'key':self.key,
            'xml':'<p>100</p>','base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']}))
        self.assertEqual(self.remote.writes,1)

    def test_range_push_preserves_media_and_comments(self):
        self.authored_create('<h1>主策 Debrief</h1><p>100</p><whiteboard token="board_token"/>',
            {self.key:{'start':1,'end':2}})
        data=self.pull();body={'key':self.key,'xml':'<p>100</p>',
            'base_revision':data['remote_revision'],'expected_local_revision':self.review['revision_id']}
        self.code('COLLAB_RESOURCE_LOSS',lambda:self.runcommand('collab.push',body))
        self.remote.snapshot['reference_map']={'comments':['团队评论']};self.remote.snapshot['revision']+=1;data=self.pull()
        self.code('COLLAB_COMMENT_PROTECTED',lambda:self.runcommand('collab.push',{**body,
            'xml':'<p>100</p><whiteboard token="board_token"/>','base_revision':data['remote_revision']}))
        self.assertEqual(self.remote.writes,1)

    def test_missing_media_on_readback_cannot_be_acknowledged(self):
        self.authored_create('<p>100</p><whiteboard token="board_token"/>',{self.key:{'start':0,'end':1}})
        self.update('80');self.publish('80');data=self.pull();original=self.remote.write
        def drop_media(args,xml):
            result=original(args,xml)
            self.remote.snapshot['content']=''.join(ET.tostring(n,encoding='unicode') for n in c.nodes(self.remote.snapshot) if n.tag!='whiteboard')
            return result
        with patch('yuplus.collaboration.remote_write',drop_media):
            self.code('COLLAB_WRITE_UNCERTAIN',lambda:self.runcommand('collab.push',{'key':self.key,
                'xml':'<p>80</p><whiteboard token="board_token"/>','base_revision':data['remote_revision'],
                'expected_local_revision':self.review['revision_id']}))
        self.assertTrue(self.runcommand('collab.show')['data']['binding']['local_pending'])
