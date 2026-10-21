"""Atomic draft editing with evidence, decisions and stable item identities."""
import copy
from datetime import date, datetime
import json
from .core import (YuError, canonical, digest, new_id, now, insert, scoped_row, get_object,
                   load_revision, resolve_dependency, revision_content, write_revision, affected_objects)

def unique(values,label):
    if len(values)!=len(set(values)):raise YuError('INVALID_INPUT',label+'不能重复。')

def check_source(ctx,sid):
    s=scoped_row(ctx.db,'source_versions',ctx.project_id,sid,'SOURCE_NOT_FOUND')
    if not s['sealed']:raise YuError('INVALID_ITEM_REFERENCE','来源尚未封存。')
    return s

def normalize_sources(ctx,refs):
    unique([s['evidence_id'] for s in refs],'evidence_id')
    result=[]
    for s in refs:
        check_source(ctx,s['source_version_id'])
        if s.get('asset_id') and not ctx.db.execute('SELECT 1 FROM source_files WHERE project_id=? AND source_version_id=? AND asset_id=?',(ctx.project_id,s['source_version_id'],s['asset_id'])).fetchone():
            raise YuError('INVALID_ITEM_REFERENCE','附件不属于所指来源快照。')
        loc=s.get('locator',{})
        for k in ('page','page_start','page_end'):
            if k in loc and (type(loc[k]) is not int or loc[k]<1):raise YuError('INVALID_ITEM_REFERENCE','页码必须为正整数。')
        result.append({**s,'locator':loc})
    return sorted(result,key=lambda s:s['evidence_id'])

def _items_for_type(ctx,typ,planned):
    for p in planned.values():
        if p['op']['type_key']==typ:return p['items']
    o=ctx.db.execute("SELECT current_revision_id FROM objects WHERE project_id=? AND layer='draft' AND type_key=? AND scope_key='project' AND archived_at IS NULL",(ctx.project_id,typ)).fetchone()
    return {i['item_id']:i for i in load_revision(ctx.db,ctx.project_id,o['current_revision_id'])['payload']['items']} if o and o['current_revision_id'] else {}

def _data_rules(ctx,typ,scope,item,planned):
    data=item['data']
    if typ in {'budget_range','budget_allocation'}:
        amounts=[k for k in ('min_minor','max_minor','amount_minor') if k in data]
        if amounts and not data.get('currency'):raise YuError('INVALID_MONEY','提供金额时需要币种。')
        if 'min_minor' in data and 'max_minor' in data and int(data['min_minor'])>int(data['max_minor']):raise YuError('INVALID_MONEY','预算下限不能大于上限。')
    if typ=='milestones' and any(k in data for k in ('start','end')):
        kind=data.get('time_kind')
        try:
            if kind not in {'date','instant','range'} or 'start' not in data:raise ValueError()
            def parse(s):
                if len(s)==10:return date.fromisoformat(s)
                parsed=datetime.fromisoformat(s.replace('Z','+00:00'))
                if parsed.tzinfo is None:raise ValueError()
                return parsed
            first=parse(data['start'])
            if kind=='date' and type(first) is not date:raise ValueError()
            if kind=='instant' and type(first) is not datetime:raise ValueError()
            if kind=='range':
                last=parse(data['end'])
                if type(first) is not type(last) or last<first:raise ValueError()
            elif 'end' in data:raise ValueError()
        except (ValueError,KeyError,TypeError):raise YuError('INVALID_TIME','时间必须为真实日期或带时区的时刻，区间必须有合法起止。')
    if typ in {'deliverables','responsibilities'} and data.get('resource_item_id'):
        if data['resource_item_id'] not in _items_for_type(ctx,'resources',planned):raise YuError('INVALID_ITEM_REFERENCE','资源条目不在同项目 D19 中。')
    if typ in {'qa','open_questions'}:
        for oid in data.get('related_object_ids',[]):get_object(ctx.db,ctx.project_id,oid)
    if typ=='expression_guide':
        o=get_object(ctx.db,ctx.project_id,data['review_object_id'])
        if o['layer']!='review' or o['archived_at'] or scope!='review:'+o['id']:raise YuError('INVALID_SCOPE','编写要求必须绑定对应 review。')
        r=load_revision(ctx.db,ctx.project_id,o['current_revision_id'])
        block_ids={b['block_id'] for b in r['payload']['blocks']}
        if any(x!='*' and x not in block_ids for x in data['block_ids']):raise YuError('INVALID_ITEM_REFERENCE','编写要求引用了不存在的成果段落。')
        if not any(s['kind']=='instruction' for s in item['source_refs']):raise YuError('SOURCE_EVIDENCE_REQUIRED','编写要求必须保存用户指令来源。')

def _check_final_graph(ctx):
    graph={};itemsets={};allrevs=[]
    for o in ctx.db.execute("SELECT * FROM objects WHERE project_id=? AND layer='draft' AND archived_at IS NULL AND current_revision_id IS NOT NULL",(ctx.project_id,)).fetchall():
        r=load_revision(ctx.db,ctx.project_id,o['current_revision_id']);allrevs.append((o['id'],r))
        itemsets[o['id']]=[i['item_id'] for i in r['payload']['items']]
    for oid,r in allrevs:
        for item in r['payload']['items']:
            key=(oid,item['item_id']);graph[key]=[]
            for d in r['dependencies'].get(item['item_id'],[]):
                targets=itemsets.get(d['object_id'],[]) if d['item_id']=='*' else [d['item_id']]
                graph[key].extend((d['object_id'],t) for t in targets)
    visiting=set();done=set()
    def visit(node):
        if node in visiting:raise YuError('DEPENDENCY_CYCLE','draft 条目依赖形成循环。')
        if node in done:return
        visiting.add(node)
        for dep in graph.get(node,[]):visit(dep)
        visiting.remove(node);done.add(node)
    for node in graph:visit(node)

def _check_final_resource_references(ctx):
    resources=_items_for_type(ctx,'resources',{})
    for obj in ctx.db.execute("SELECT id,current_revision_id FROM objects WHERE project_id=? AND layer='draft' AND type_key IN ('deliverables','responsibilities') AND archived_at IS NULL",(ctx.project_id,)).fetchall():
        if not obj['current_revision_id']:continue
        for item in load_revision(ctx.db,ctx.project_id,obj['current_revision_id'])['payload']['items']:
            resource=item['data'].get('resource_item_id')
            if resource and resource not in resources:
                raise YuError('INVALID_ITEM_REFERENCE','资源仍被交付或职责引用；请在同一批次更新这些引用。',
                              details=[{'object_id':obj['id'],'item_id':item['item_id'],'resource_item_id':resource}])

def apply_draft(ctx,request):
    ops=request['objects'];unique([o['op_id'] for o in ops],'op_id')
    unique([(o['type_key'],o['scope_key']) for o in ops],'对象类型与范围')
    if request.get('instruction_source_version_id'):check_source(ctx,request['instruction_source_version_id'])
    plans={};byobject={}
    # Resolve all identities/base versions before writing any object contents.
    for op in ops:
        typ,scope=op['type_key'],op['scope_key']
        if typ!='expression_guide' and scope!='project':raise YuError('INVALID_SCOPE','普通 draft 范围必须是 project。')
        if op.get('object_id'):
            o=get_object(ctx.db,ctx.project_id,op['object_id'])
            if (o['layer'],o['type_key'],o['scope_key'])!=('draft',typ,scope):raise YuError('INVALID_SCOPE','对象身份、类型与范围不匹配。')
        else:
            row=ctx.db.execute("SELECT * FROM objects WHERE project_id=? AND layer='draft' AND type_key=? AND scope_key=?",(ctx.project_id,typ,scope)).fetchone();o=dict(row) if row else None
        if o and o['archived_at']:raise YuError('INVALID_SCOPE','不能修改已归档的对象。')
        actual=o['current_revision_id'] if o else None
        if op['base_revision']!=actual or (o is not None and op['base_revision'] is None):
            raise YuError('BASE_REVISION_CONFLICT','draft 基础版本已变化。',retryable=True,details=[{'object_id':o['id'] if o else None,'expected':op['base_revision'],'actual':actual}])
        if not o:
            oid=new_id('obj');insert(ctx.db,'objects',project_id=ctx.project_id,id=oid,layer='draft',type_key=typ,scope_key=scope,created_at=now());o=get_object(ctx.db,ctx.project_id,oid)
        old=load_revision(ctx.db,ctx.project_id,actual) if actual else None
        oldpayload=old['payload'] if old else {'title':typ,'items':[],'item_order':[]}
        items={i['item_id']:copy.deepcopy(i) for i in oldpayload['items']}
        sources=copy.deepcopy(old['sources']) if old else {};deps=copy.deepcopy(old['dependencies']) if old else {}
        sets=op.get('set_items',[]);removes=op.get('remove_items',[])
        unique([i['item_id'] for i in sets],'item_id');unique(removes,'remove_items')
        if set(removes)&{i['item_id'] for i in sets}:raise YuError('INVALID_INPUT','不能同时修改和删除同一条目。')
        for key in removes:
            if key not in items:raise YuError('INVALID_ITEM_REFERENCE','删除的条目不存在。')
            items.pop(key);sources.pop(key,None);deps.pop(key,None)
        for item in sets:
            items[item['item_id']]={k:copy.deepcopy(item[k]) for k in ('item_id','data','epistemic_kind')}
        order=op.get('item_order',[i for i in oldpayload['item_order'] if i in items]+[i['item_id'] for i in sets if i['item_id'] not in oldpayload['item_order']])
        if len(order)!=len(items) or set(order)!=set(items):raise YuError('INVALID_INPUT','item_order 必须恰好排列全部条目。')
        plan={'op':op,'object':o,'old':old,'items':items,'sources':sources,'dependencies':deps,'order':order}
        plans[op['op_id']]=plan;byobject[o['id']]=op['op_id']
    decisions=request['decisions'];unique([d['decision_key'] for d in decisions],'decision_key')
    covered=set()
    for decision in decisions:
        check_source(ctx,decision['instruction_source_version_id'])
        if not decision['statement'].strip() or not decision['decided_by'].strip():raise YuError('INVALID_INPUT','决定内容与决定者不能为空。')
        if decision.get('supersedes_id'):
            scoped_row(ctx.db,'decisions',ctx.project_id,decision['supersedes_id'],'DECISION_NOT_FOUND')
            if ctx.db.execute('SELECT 1 FROM decisions WHERE project_id=? AND supersedes_id=?',(ctx.project_id,decision['supersedes_id'])).fetchone():raise YuError('BASE_REVISION_CONFLICT','该决定已有后继，请引用最新决定。')
        for ref in decision['affected_items']:
            plan=plans.get(ref['op_id'])
            if not plan or (ref['item_id'] not in plan['items'] and ref['item_id'] not in plan['op'].get('remove_items',[])):raise YuError('INVALID_ITEM_REFERENCE','决定引用的本批次条目不存在。')
            covered.add((ref['op_id'],ref['item_id']))
    # Topological order of operations, including explicit existing-object dependencies.
    graph={key:set() for key in plans}
    for key,plan in plans.items():
        for item in plan['op'].get('set_items',[]):
            for d in item['dependencies']:
                producer=d.get('op_id',byobject.get(d.get('object_id')))
                if 'op_id' in d and producer not in plans:raise YuError('INVALID_ITEM_REFERENCE','依赖的 op_id 不存在。')
                if producer==key and 'op_id' in d:raise YuError('DEPENDENCY_CYCLE','不能依赖本操作尚未生成的版本。')
                if producer and producer!=key:graph[key].add(producer)
    ordered=[];visiting=set();done=set()
    def visit(key):
        if key in visiting:raise YuError('DEPENDENCY_CYCLE','批次依赖形成循环。')
        if key in done:return
        visiting.add(key)
        for p in graph[key]:visit(p)
        visiting.remove(key);done.add(key);ordered.append(key)
    for key in plans:visit(key)
    results={};actually_changed=set()
    for key in ordered:
        plan=plans[key];op=plan['op'];old=plan['old'];sources=plan['sources'];deps=plan['dependencies']
        changed=set(op.get('remove_items',[]))
        olditems={i['item_id']:i for i in old['payload']['items']} if old else {}
        for iid in op.get('remove_items',[]):
            if olditems[iid]['epistemic_kind']=='adopted_decision' and (key,iid) not in covered:
                raise YuError('DECISION_REQUIRED','删除已采用的条目需要记录新的决定。')
        for item in op.get('set_items',[]):
            iid=item['item_id'];sources[iid]=normalize_sources(ctx,item['source_refs'])
            unique([d['dependency_id'] for d in item['dependencies']],'dependency_id')
            resolved=[]
            for dependency in item['dependencies']:
                d=copy.deepcopy(dependency)
                if 'op_id' in d:
                    producer=results[d.pop('op_id')];d.update(object_id=producer['object_id'],revision_id=producer['revision_id'])
                resolved.append(resolve_dependency(ctx,d))
            deps[iid]=sorted(resolved,key=lambda d:d['dependency_id'])
            entry_changed=(olditems.get(iid)!=plan['items'][iid] or (old['sources'].get(iid,[]) if old else [])!=sources[iid] or (old['dependencies'].get(iid,[]) if old else [])!=deps[iid])
            if entry_changed:
                changed.add(iid)
                if (item['epistemic_kind']=='adopted_decision' or olditems.get(iid,{}).get('epistemic_kind')=='adopted_decision') and (key,iid) not in covered:raise YuError('DECISION_REQUIRED','采用或修改决定需要同步记录决定。')
                if item['epistemic_kind'] in {'source_statement','user_supplied','reported'} and not sources[iid]:raise YuError('SOURCE_EVIDENCE_REQUIRED','事实或转述需要来源。')
            _data_rules(ctx,op['type_key'],op['scope_key'],item,plans)
        payload={'title':op.get('title',old['payload']['title'] if old else op['type_key']),'items':[plan['items'][i] for i in plan['order']],'item_order':plan['order']}
        substantive=revision_content(payload,sources,deps)
        if old and digest(substantive)==old['content_hash']:
            result={'object_id':plan['object']['id'],'revision_id':old['id'],'version':old['version'],'changed':False}
        else:
            if old and (payload['title']!=old['payload']['title'] or payload['item_order']!=old['payload']['item_order']):changed.add('*')
            result={**write_revision(ctx,plan['object']['id'],payload,sources=sources,dependencies=deps,changed_items=sorted(changed) or ['*']),'changed':True}
            actually_changed.update((key,i) for i in changed)
        results[key]={**result,'op_id':key}
    _check_final_graph(ctx)
    _check_final_resource_references(ctx)
    records=[]
    for decision in decisions:
        affected=[]
        for ref in decision['affected_items']:
            result=results[ref['op_id']]
            affected.append({'object_id':result['object_id'],'revision_id':result['revision_id'],'item_id':ref['item_id']})
        if any((r['op_id'],r['item_id']) not in actually_changed for r in decision['affected_items']):
            # Re-submitting the same adopted facts should not manufacture a decision.
            wanted={(r['object_id'],r['item_id']) for r in affected}
            prior=ctx.db.execute('SELECT * FROM decisions WHERE project_id=? AND statement=? AND decided_by=? AND user_instruction_source_version_id=? AND rationale=? AND supersedes_id IS ?',
                                 (ctx.project_id,decision['statement'],decision['decided_by'],decision['instruction_source_version_id'],decision['rationale'],decision.get('supersedes_id'))).fetchall()
            if not any(results[r['op_id']]['changed'] for r in decision['affected_items']) and any({(r['object_id'],r['item_id']) for r in json.loads(d['affected_refs_json'])}==wanted for d in prior):
                continue
            raise YuError('INVALID_ITEM_REFERENCE','新决定必须对应本批次实际发生的条目变化。')
        did=new_id('dec')
        insert(ctx.db,'decisions',project_id=ctx.project_id,id=did,change_id=ctx.change_id,statement=decision['statement'],decided_by=decision['decided_by'],
               user_instruction_source_version_id=decision['instruction_source_version_id'],rationale=decision['rationale'],affected_refs_json=canonical(affected),supersedes_id=decision.get('supersedes_id'),created_at=now())
        records.append({'decision_key':decision['decision_key'],'decision_id':did})
    impacts=affected_objects(ctx.db,ctx.project_id)
    return {'effect':'changed' if any(r['changed'] for r in results.values()) else 'noop','objects':[results[o['op_id']] for o in ops],
            'decisions':records,'affected_reviews':impacts['review'],'affected_draft_items':impacts['draft']}
