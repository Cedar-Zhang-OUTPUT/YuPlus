#!/usr/bin/env python3
"""Repeatable real CLI/HTTP acceptance using synthetic, clearly labelled material.

seed saves a pending draft→review change for browser inspection; finish publishes
all affected review instances and prepares a local export. No Feishu writes.
"""
from __future__ import annotations
import argparse
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

from demo_chain import Demo


def item(ident, data, source):
    return {'item_id':ident, 'data':data, 'epistemic_kind':'user_supplied',
            'source_refs':[{'evidence_id':'ev_'+ident, 'source_version_id':source, 'kind':'instruction'}], 'dependencies':[]}


def source(d, text, key, assets=()):
    return d.call('source.import', key=key, request={
        'api_version':'1','command':'source.import',
        'target':{'mode':'create','provider':'oral' if not assets else 'local','resource_type':'statement' if not assets else 'file'},
        'snapshot':{'title':'合成验收材料 · '+key,'provider_revision':None,'captured_at':'2026-10-16T03:00:00Z',
                    'capture_scope':{'kind':'whole_resource'},'extraction_profile':'acceptance-verbatim-v1',
                    'body':{'format':'text','text':text},'provenance':{'method':'synthetic-test-fixture'},'assets':list(assets)},
        'advance_head':True,'reason':'集成验收：保存明确标注的合成材料'})['data']


def prepare(d, target, basis, causes=()):
    return d.call('review.prepare', request={'api_version':'1','command':'review.prepare','target':target,
        'cause_change_ids':list(causes), 'select_basis':basis})['data']


def seed(root):
    root.mkdir(parents=True, exist_ok=True)
    if (root/'state.json').exists():
        raise RuntimeError('该目录已有验收记录；使用新目录，避免覆盖。')
    d=Demo(root/'data')
    pid=d.call('project.create',key='create',flags=('--name','Yu+ 真实链路验收（合成资料）'))['data']['project_id']
    other=d.call('project.create',key='other',flags=('--name','隔离检查 · 空项目'))['data']['project_id']
    d.project_id=pid
    material=root/'验收原件.txt'
    text='这是自动验收使用的合成资料，不是真实客户项目。视频团队本轮交成片；视觉团队交展墙图。两组仅供测试。客户答复：使用现有场地。'
    material.write_text(text)
    png=root/'验收图片.png'
    png.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII='))
    assets=[{'asset_id':ident,'role':'original','display_name':path.name,'mime_type':mime,'local_path':str(path),'storage':'copy'}
            for ident,path,mime in [('original',material,'text/plain'),('photo',png,'image/png')]]
    imported=source(d,text,'initial',assets)
    sid=imported['snapshot_id']
    defs={
      'deliverables':[item('film',{'deliverable':'成片','round_key':'r1','resource_item_id':'video_team','format':'MP4'},sid),
                      item('wall',{'deliverable':'展墙图','round_key':'r1','resource_item_id':'visual_team','format':'PDF'},sid)],
      'resources':[item('video_team',{'name':'验收视频团队','participation':'confirmed'},sid),item('visual_team',{'name':'验收视觉团队','participation':'candidate'},sid)],
      'qa':[item('venue_answer',{'question':'是否使用现有场地？','answer':'使用现有场地。','status':'answered'},sid)],
      'milestones':[item('delivery_day',{'event':'提交初稿','time_kind':'date','start':'2026-10-20'},sid),
                    item('review_minute',{'event':'测试 Review','time_kind':'instant','start':'2026-10-21T14:30+08:00','timezone':'Asia/Shanghai'},sid)],
      'lead_strategy':[item('strategy',{'topic':'验收策略','strategy':'仅核验流程，不产生真实策划结论。'},sid)]}
    result=d.call('draft.apply',key='draft',request={'api_version':'1','command':'draft.apply','reason':'按合成材料记录对象',
        'objects':[{'op_id':kind,'type_key':kind,'scope_key':'project','base_revision':None,'set_items':items} for kind,items in defs.items()], 'decisions':[]})
    objects={r['type_key'] if 'type_key' in r else r['op_id']:r for r in result['data']['objects']}
    docs=[]
    def publish(kind,scope,blocks):
        target={'type_key':kind,'scope_key':scope}
        selection={}
        mapped=[]
        for blockid,markdown,typekey,itemid in blocks:
            obj=objects[typekey]; selection.setdefault(obj['object_id'],[]).append(itemid)
            mapped.append({'block_id':blockid,'markdown':markdown,'cause_change_ids':[],
                'dependencies':[{'dependency_id':'dep_'+blockid,'object_id':obj['object_id'],'revision_id':obj['revision_id'],'item_id':itemid,'kind':'fact'}]})
        basis=[{'object_id':oid,'item_ids':ids} for oid,ids in selection.items()]
        ready=prepare(d,target,basis)
        doc={'target':target,'base_revision':None,'title':'合成验收 · '+kind+' · '+scope,'read_basis':ready['read_basis'],
             'structure_cause_change_ids':[],'set_blocks':mapped}
        saved=d.call('review.publish',key='review_'+str(len(docs)),request={'api_version':'1','command':'review.publish','reason':'生成合成验收成果','documents':[doc]})['data']['documents'][0]
        docs.append({'saved':saved,'document':doc,'basis':basis})
    publish('debrief','project',[('film_scope','## 视频交付\n本轮交付 **成片**。','deliverables','film'),('wall_scope','## 视觉交付\n本轮交付展墙图。','deliverables','wall')])
    publish('advancement','project',[('timeline','2026-10-20 提交初稿。','milestones','delivery_day')])
    publish('creative_review','project',[('strategy','仅核验流程，不产生真实策划结论。','lead_strategy','strategy')])
    publish('creator_brief','creator:video_team:round:r1',[('film_scope','视频团队本轮交付成片。','deliverables','film')])
    publish('creator_brief','creator:visual_team:round:r1',[('wall_scope','视觉团队本轮交付展墙图。','deliverables','wall')])
    # Verify bypass rejection before introducing a real cause.
    illegal=copy.deepcopy(docs[0]['document']); illegal['target']['object_id']=docs[0]['saved']['object_id']; illegal['base_revision']=docs[0]['saved']['revision_id']
    illegal['set_blocks'][0]['markdown']='绕过 draft 的非法修改'
    refused=d.call('review.publish',key='refused',expected_code=5,request={'api_version':'1','command':'review.publish','reason':'验收因果约束','documents':[illegal]})
    assert refused['error']['code']=='DRAFT_CHANGE_REQUIRED', refused
    instruction=source(d,'合成验收修改指令：视频团队这轮只交概念脚本，不交成片；展墙图要求不变。','change')
    delivery=objects['deliverables']
    changed=d.call('draft.apply',key='draft_change',request={'api_version':'1','command':'draft.apply','reason':'验收：只改视频交付',
        'objects':[{'op_id':'delivery','type_key':'deliverables','scope_key':'project','object_id':delivery['object_id'],
           'base_revision':delivery['revision_id'],'set_items':[item('film',{'deliverable':'概念脚本','round_key':'r1','resource_item_id':'video_team','format':'文档'},instruction['snapshot_id'])]}], 'decisions':[]})
    state={'project_id':d.project_id,'other_project_id':other,'data_dir':str(d.data_dir),'objects':objects,'documents':docs,
           'source':imported,'change':changed,'phase':'pending_review'}
    (root/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
    print(json.dumps({'phase':state['phase'],'project_id':d.project_id,'data_dir':str(d.data_dir),'review_object_id':docs[0]['saved']['object_id']},ensure_ascii=False))


def check_http(state,url):
    def get(path):
        with urlopen(url+path,timeout=15) as response:return json.load(response)
    view=get('/api/view?project='+state['project_id'])
    assert view['meta']['demo'] is False
    assert len([o for o in view['objects'] if o['layer']=='review'])==5
    assert len([o for o in view['objects'] if o['type_key']=='qa'])==1
    old=state['objects']['deliverables']
    assert view['basis_status_by_key'][f"{old['object_id']}:{old['revision_id']}:film"]=='changed'
    assert view['basis_status_by_key'][f"{old['object_id']}:{old['revision_id']}:wall"]=='same'
    assert not get('/api/view?project='+state['other_project_id'])['objects']
    saved=next(v for v in view['source_versions'] if v['id']==state['source']['snapshot_id'])
    for asset in saved['assets']:
        assert asset['availability']=='available'
        with urlopen(url+asset['url']) as response:assert len(response.read())==asset['size_bytes']
    return view


def finish(root,url):
    state=json.loads((root/'state.json').read_text())
    if state['phase']!='pending_review':raise RuntimeError('验收已完成。请用新目录重新 seed。')
    check_http(state,url)
    d=Demo(Path(state['data_dir']));d.project_id=state['project_id']
    cause=state['change']['meta']['change_id']
    new=state['change']['data']['objects'][0]
    for entry in state['documents']:
        if not any(dep['item_id']=='film' for b in entry['document']['set_blocks'] for dep in b['dependencies']):continue
        doc=copy.deepcopy(entry['document']);doc['target']['object_id']=entry['saved']['object_id'];doc['base_revision']=entry['saved']['revision_id']
        ready=prepare(d,doc['target'],entry['basis'],[cause]);doc['read_basis']=ready['read_basis']
        changed=[]
        for block in doc['set_blocks']:
            if not any(dep['item_id']=='film' for dep in block['dependencies']):continue
            block['markdown']=block['markdown'].replace('成片','概念脚本');block['cause_change_ids']=[cause]
            for dep in block['dependencies']:dep['revision_id']=new['revision_id']
            changed.append(block)
        doc['set_blocks']=changed
        result=d.call('review.publish',key=entry['saved']['object_id'],request={'api_version':'1','command':'review.publish','reason':'按已保存 draft 更新交付成果','documents':[doc]})
        entry['updated']=result['data']['documents'][0]
    check_http(state,url)
    # All *current* review bases must now be fresh; old saved review bases remain changed.
    with urlopen(url+'/api/view?project='+d.project_id) as response:view=json.load(response)
    heads={o['current_revision_id'] for o in view['objects'] if o['layer']=='review'}
    for rev in view['object_revisions']:
        if rev['id'] in heads:
            assert all(dep['status']=='same' for b in rev['payload']['blocks'] for dep in b['dependencies'])
    result=subprocess.run([sys.executable,'-m','yuplus.export_bundle','--data-dir',state['data_dir'],'--project',d.project_id,'--output',str(root/'export')],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    state['phase']='complete';state['service_url']=url
    (root/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
    print(result.stdout)
    print('PASS: real CLI → HTTP/assets → scoped impact → review update → historical evidence → full local export')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['seed','finish']);p.add_argument('--root',type=Path,required=True);p.add_argument('--url')
    args=p.parse_args();root=args.root.expanduser().resolve()
    if args.phase=='seed':seed(root)
    else:
        if not args.url:p.error('finish requires --url')
        finish(root,args.url)
