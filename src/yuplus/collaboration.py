"""Durable collaboration inbox and optimistic, section-scoped Feishu publication.

The service observes. Agents interpret evidence through the ordinary draft/review
commands; no remote edit is a business decision merely because it is newer.
"""
from contextlib import contextmanager
import fcntl
import json
import re
from html import escape
import xml.etree.ElementTree as ET
from .core import YuError, canonical, digest, now, load_revision, is_fresh
from .feishu import run_lark

ACTIONS={'create','bind','show','pull','pending','prepare','push','accept','resolve','pause','resume','scheduler-bind','schedule','step','map'}
OUTLINES={
 'debrief':['项目任务','受众与场景','主策判断','本轮创意任务','边界与判断标准'],
 'advancement':['本轮交付与分工','时间节点与区间','讨论与评审安排'],
 'creative_plan':['核心概念','如何回应项目任务','叙事与体验','视觉与案例参考','深化内容','待讨论事项'],
 'creative_review':['本轮评审对象','反馈与判断','取舍与结论','下一轮修改']}
NAMES={'debrief':'主策 Debrief','advancement':'项目推进安排','creative_plan':'创意方案','creative_review':'创意评审记录','qa':'客户 Q&A'}

def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS collaboration_docs (
      project_id TEXT PRIMARY KEY REFERENCES projects(id), url TEXT NOT NULL UNIQUE,
      enabled INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
      observed_json TEXT, baseline_json TEXT NOT NULL DEFAULT '{}', mappings_json TEXT NOT NULL DEFAULT '{}',
      schedule_json TEXT NOT NULL DEFAULT '{}', last_checked_at TEXT, last_synced_at TEXT,
      error_json TEXT, created_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS collaboration_events (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), fingerprint TEXT NOT NULL,
      snapshot_json TEXT NOT NULL, source_snapshot_id TEXT, state TEXT NOT NULL DEFAULT 'pending',
      resolution_json TEXT, created_at TEXT NOT NULL, UNIQUE(project_id,fingerprint))''')
    db.execute('''CREATE TABLE IF NOT EXISTS collaboration_operations (
      project_id TEXT NOT NULL REFERENCES projects(id), request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
      state TEXT NOT NULL, input_json TEXT NOT NULL, result_json TEXT, created_at TEXT NOT NULL,
      PRIMARY KEY(project_id,request_id))''')

@contextmanager
def lock(app,pid):
    # Shared with all CLI business writers, held during a remote patch. No shell.
    path=app.data_dir/'locks';path.mkdir(exist_ok=True)
    with (path/(digest(pid)+'.lock')).open('a') as stream:
        try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise YuError('PROJECT_BUSY','项目正在同步，请稍后重试。') from None
        try: yield
        finally: fcntl.flock(stream,fcntl.LOCK_UN)

def get(db,pid):
    row=db.execute('SELECT * FROM collaboration_docs WHERE project_id=?',(pid,)).fetchone()
    if not row: raise YuError('COLLAB_NOT_BOUND','尚未建立飞书协作文档。')
    return dict(row)

def public(db,pid):
    row=db.execute('SELECT * FROM collaboration_docs WHERE project_id=?',(pid,)).fetchone()
    if not row:return None
    r=dict(row)
    r['schedule']=json.loads(r.pop('schedule_json'));r['error']=json.loads(r.pop('error_json') or 'null')
    r['pending']=db.execute("SELECT count(*) FROM collaboration_events WHERE project_id=? AND state='pending'",(pid,)).fetchone()[0]
    r['conflicts']=db.execute("SELECT count(*) FROM collaboration_events WHERE project_id=? AND state='conflict'",(pid,)).fetchone()[0]
    base=json.loads(r.pop('baseline_json'));r['local_pending']=base.get('local')!=local_sections(db,pid) if base else True
    r.pop('observed_json');r.pop('mappings_json')
    r['records']=[dict(x) for x in db.execute('SELECT id,state,resolution_json,created_at FROM collaboration_events WHERE project_id=? ORDER BY created_at DESC LIMIT 20',(pid,))]
    return r

def valid_url(url):
    from urllib.parse import urlsplit
    try:
        p=urlsplit(url)
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not any(p.hostname==d or p.hostname.endswith('.'+d) for d in ('feishu.cn','larksuite.com')) or not re.fullmatch('/docx/[A-Za-z0-9_-]+',p.path):raise ValueError()
    except (ValueError,TypeError,AttributeError):raise YuError('INVALID_INPUT','需要飞书 docx 文档链接。') from None
    return url.split('?')[0].split('#')[0]

def local_sections(db,pid):
    result={}
    rows=db.execute("SELECT * FROM objects WHERE project_id=? AND archived_at IS NULL AND (layer='review' OR type_key='qa') ORDER BY type_key,scope_key,id",(pid,)).fetchall()
    for o in rows:
        if not o['current_revision_id']:continue
        r=load_revision(db,pid,o['current_revision_id'])
        entries=r['payload'].get('blocks',r['payload'].get('items',[]))
        for b in entries:
            key=o['id']+':'+b.get('block_id',b.get('item_id'))
            if o['type_key']=='qa':
                d=b['data'];md='## '+d.get('question','客户问题')+'\n\n'+d.get('answer','待答复')
                for field,label in [('asked_by','提问人'),('answered_by','回答方'),('follow_up_person','跟进人')]:
                    if d.get(field):md+='\n\n'+label+'：'+d[field]
            else:md=b['markdown']
            result[key]={'object_id':o['id'],'revision_id':r['id'],'block_id':b.get('block_id',b.get('item_id')),'type_key':o['type_key'],'title':r['payload'].get('title') or NAMES.get(o['type_key'],o['type_key']),'markdown':md,'hash':digest(md)}
    return result

def fetch(url):
    data=run_lark(['docs','+fetch','--as','user','--doc',url,'--detail','with-ids'])
    d=data.get('document',{})
    if type(d.get('revision_id')) is not int or not isinstance(d.get('content'),str):raise YuError('FEISHU_UNAVAILABLE','未返回完整文档与版本。')
    # Includes comments returned by the adapter; resource payloads require their own reads.
    return {'revision':d['revision_id'],'content':d['content'],'reference_map':d.get('reference_map',{})}

def nodes(snapshot):
    try:root=ET.fromstring('<root>'+snapshot['content']+'</root>')
    except ET.ParseError:raise YuError('COLLAB_PARSE_FAILED','无法解析飞书内容，保留原文，未执行回写。') from None
    return list(root)

def normalized(xml):
    # IDs and generated ordinal attributes are transport identity, not author content.
    return re.sub(r'\s(?:id|seq|seq-marker)="[^"]*"','',xml)

def sections(snapshot,mappings):
    items=nodes(snapshot); positions={n.get('id'):i for i,n in enumerate(items) if n.get('id')}
    mapped={v for v in mappings.values()};result={}
    for key,anchor in mappings.items():
        if anchor not in positions:result[key]=None;continue
        start=positions[anchor];end=start+1
        while end<len(items) and items[end].get('id') not in mapped and items[end].tag!='h1':end+=1
        group=items[start:end];xml=''.join(ET.tostring(n,encoding='unicode') for n in group)
        result[key]={'start':anchor,'end':group[-1].get('id'),'xml':xml,'hash':digest(normalized(xml))}
    return result

def changes(base,local,remote):
    """Three-way classification; absence is a real change, not an empty value."""
    result={}
    for key in base.get('local',{}).keys()|local.keys()|remote.keys():
        a=base.get('local',{}).get(key,{}).get('hash');b=local.get(key,{}).get('hash')
        c=(base.get('remote',{}).get(key) or {}).get('hash');d=(remote.get(key) or {}).get('hash')
        lc=a!=b;rc=c!=d
        result[key]='conflict' if lc and rc else 'remote' if rc else 'local' if lc else 'same'
    return result

def read_pending(db,pid):
    return [dict(r)|{'snapshot':json.loads(r['snapshot_json'])} for r in db.execute("SELECT * FROM collaboration_events WHERE project_id=? AND state IN ('pending','conflict') ORDER BY created_at",(pid,))]

def observe(app,pid,reader=None):
    reader=reader or fetch
    row=get(app.db,pid)
    if not row['enabled']:return {'paused':True}
    snapshot=reader(row['url']);fp=digest(snapshot)
    # Import a version once; generated writes are acknowledged by exact observed content.
    last=json.loads(row['observed_json'] or 'null')
    if last!=snapshot:
        eid='evt_'+digest([pid,fp])[:32]
        app.db.execute('INSERT OR IGNORE INTO collaboration_events(id,project_id,fingerprint,snapshot_json,created_at) VALUES(?,?,?,?,?)',(eid,pid,fp,canonical(snapshot),now()))
        app.db.execute('UPDATE collaboration_docs SET observed_json=?,last_checked_at=?,error_json=NULL WHERE project_id=?',(canonical(snapshot),now(),pid))
    else:app.db.execute('UPDATE collaboration_docs SET last_checked_at=?,error_json=NULL WHERE project_id=?',(now(),pid))
    return {'snapshot':snapshot,'pending':read_pending(app.db,pid)}

def validate_xml(xml):
    if not isinstance(xml,str) or not xml.strip():raise YuError('INVALID_INPUT','章节 XML 不能为空。')
    try: root=ET.fromstring('<root>'+xml+'</root>')
    except ET.ParseError:raise YuError('INVALID_INPUT','章节 XML 无法解析。') from None
    if any(n.tag in {'h1','title'} for n in root):raise YuError('INVALID_INPUT','章节内使用二级及以下标题；一级标题由映射管理。')
    return root

def markdown_xml(text):
    # Safe initial projection. Media and Gantt must be authored by Agent using native XML.
    out=[]
    for para in text.split('\n'):
        if not para.strip():continue
        m=re.match(r'^#{1,6}\s+(.*)',para)
        out.append('<h2>'+escape(m[1])+'</h2>' if m else '<p>'+escape(para)+'</p>')
    return ''.join(out)

def remote_write(args,xml):
    result=run_lark(['docs',*args,'--as','user','--doc-format','xml','--content','-'],timeout=120,input_text=xml)
    return result

def receipt_start(app,pid,request,payload):
    if not isinstance(request,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}',request):raise YuError('INVALID_INPUT','写操作需要 request-id。')
    fp=digest(payload);r=app.db.execute('SELECT * FROM collaboration_operations WHERE project_id=? AND request_id=?',(pid,request)).fetchone()
    if r:
        if r['fingerprint']!=fp:raise YuError('IDEMPOTENCY_CONFLICT','同一请求不能换内容。')
        if r['state']=='complete':return json.loads(r['result_json'])
        raise YuError('COLLAB_WRITE_UNCERTAIN','上次操作未完成。先 pull 回读并核实；不要盲目重复远端写入。')
    app.db.execute('INSERT INTO collaboration_operations VALUES(?,?,?,?,?,?,?)',(pid,request,fp,'started',canonical(payload),None,now()))

def execute(app,command,p,pid,request):
    action=command.split('.')[1]
    if action not in ACTIONS or not isinstance(p,dict):raise YuError('INVALID_INPUT','无效协作命令。')
    app._project(pid,write=action not in {'show','pending','schedule'})
    allowed={'show':set(),'pending':set(),'schedule':set(),'pull':set(),'prepare':set(),
       'create':{'sections'},'bind':{'url','mappings'},'push':{'key','xml','base_revision','expected_local_revision'},
       'accept':{'event_id','change_ids','outcome','reason','handled_keys'},'resolve':{'event_id','instruction_source_version_id','choice','reason'},
       'map':{'mappings'},'pause':set(),'resume':set(),'scheduler-bind':{'schedule'},'step':{'event_id','command','input'}}[action]
    if set(p)-allowed:raise YuError('INVALID_INPUT','协作命令含未知字段。')
    if len(canonical(p).encode('utf-8'))>8*1024*1024:raise YuError('INVALID_INPUT','协作输入超过 8 MiB。')
    required={'create':['sections'],'bind':['url'],'map':['mappings'],
      'push':['key','xml','base_revision','expected_local_revision'],
      'accept':['event_id','outcome','reason','handled_keys'],
      'resolve':['event_id','instruction_source_version_id','choice','reason'],
      'scheduler-bind':['schedule'],'step':['event_id','command','input']}.get(action,[])
    if any(k not in p for k in required):raise YuError('INVALID_INPUT','缺少协作命令必需字段。')
    for k in ('url','key','xml','expected_local_revision','event_id','outcome','reason','instruction_source_version_id','choice','command'):
        if k in p and (not isinstance(p[k],str) or not p[k].strip()):raise YuError('INVALID_INPUT',k+' 需要非空字符串。')
    if 'base_revision' in p and (type(p['base_revision']) is not int or p['base_revision']<0):raise YuError('INVALID_INPUT','base_revision 需要非负整数。')
    if action=='step' and not isinstance(p['input'],dict):raise YuError('INVALID_INPUT','input 需要命令 JSON 对象。')
    if action=='show':return app._envelope(command,pid,None,{'binding':public(app.db,pid),'local':local_sections(app.db,pid)})
    if action=='pending':return app._envelope(command,pid,None,{'events':read_pending(app.db,pid)})
    if action=='schedule':return app._envelope(command,pid,None,{'suggested_interval_minutes':5,'requires_host_automation_tool':True,'prompt':f'用 Yu+ 同步项目 {pid} 已绑定的飞书协作文档。按需读取 Yu+ references/collaboration.md，复用已读上下文；用数据目录 {json.dumps(str(app.data_dir),ensure_ascii=False)} 执行 collab pull，检查 pending/conflicts/local_pending。先吸收远端变化到 draft，再更新 review；解决后局部回写本地待同步内容。暂停项目不再处理；无变化保持安静，仅在实质变化、需用户选择或持续失败时通知。','schedule':json.loads(get(app.db,pid)['schedule_json'])})
    with lock(app,pid):
        return _execute_locked(app,action,command,p,pid,request)

def _execute_locked(app,action,command,p,pid,request):
    if action in {'pull','prepare'}:
        observation=observe(app,pid);row=get(app.db,pid)
        if observation.get('paused'):return app._envelope(command,pid,None,observation)
        for event in observation['pending']:
            if event['source_snapshot_id']:continue
            source={'api_version':'1','command':'source.import','target':{'mode':'create','provider':'feishu','resource_type':'docx','provider_key':row['url'].rsplit('/',1)[-1],'canonical_url':row['url']},'snapshot':{'title':'项目创意协作文档','provider_revision':str(event['snapshot']['revision']),'captured_at':event['created_at'],'capture_scope':{'kind':'whole_resource'},'extraction_profile':'collaboration-xml-v1','body':{'format':'text','text':event['snapshot']['content']+'\n'+canonical(event['snapshot'].get('reference_map',{}))},'provenance':{'method':'lark-cli-docs-fetch'}},'advance_head':True,'reason':'保存协作文档变化原文'}
            old=app.db.execute('SELECT id,latest_snapshot_id FROM sources WHERE project_id=? AND canonical_url=? AND archived_at IS NULL',(pid,row['url'])).fetchone()
            if old:source['target']={'mode':'append','source_id':old[0],'base_snapshot_id':old[1]}
            result=app.execute('source.import',source,project_id=pid,request_id='capture_'+event['id'],_project_lock=False)
            app.db.execute('UPDATE collaboration_events SET source_snapshot_id=? WHERE id=?',(result['data']['snapshot_id'],event['id']))
        local=local_sections(app.db,pid);remote=sections(observation['snapshot'],json.loads(row['mappings_json']));base=json.loads(row['baseline_json'])
        states=changes(base,local,remote)
        if 'conflict' in states.values() and not any(e.get('resolution_json') for e in observation['pending']):
            app.db.execute("UPDATE collaboration_events SET state='conflict' WHERE project_id=? AND state='pending'",(pid,))
        return app._envelope(command,pid,None,{'remote_revision':observation['snapshot']['revision'],'local':local,'remote':remote,'classification':states,'events':read_pending(app.db,pid),'mappings':json.loads(row['mappings_json'])})
    # Domain steps retain the existing atomic draft/review causality validation.
    if action=='step':
        event=app.db.execute("SELECT * FROM collaboration_events WHERE project_id=? AND id=? AND state IN ('pending','conflict')",(pid,p.get('event_id'))).fetchone()
        if not event or not event['source_snapshot_id']:raise YuError('INVALID_INPUT','先 pull 获取有效变化及来源快照。')
        if p.get('command') not in {'draft.apply','review.publish','source.import'}:raise YuError('INVALID_INPUT','不支持该协作写操作。')
        return app.execute(p['command'],p['input'],project_id=pid,request_id=request,_project_lock=False)
    replay=receipt_start(app,pid,request,{'command':command,**p})
    if replay is not None:return app._envelope(command,pid,request,replay,replayed=True)
    try:
        data=mutate(app,action,p,pid)
    except YuError as exc:
        if action not in {'create','push'}:app.db.execute('DELETE FROM collaboration_operations WHERE project_id=? AND request_id=?',(pid,request))
        raise
    app.db.execute("UPDATE collaboration_operations SET state='complete',result_json=? WHERE project_id=? AND request_id=?",(canonical(data),pid,request))
    return app._envelope(command,pid,request,data)

def mutate(app,action,p,pid):
    db=app.db
    if action in {'create','bind'}:
        if db.execute('SELECT 1 FROM collaboration_docs WHERE project_id=?',(pid,)).fetchone():return public(db,pid)
        local=local_sections(db,pid)
        if action=='create':
            if not local:raise YuError('COLLAB_NO_CONTENT','先保存有依据的策划文档，再创建协作文档。')
            authored=p.get('sections',{})
            if not isinstance(authored,dict) or set(authored)!=set(local):raise YuError('INVALID_INPUT','sections 必须按 prepare/show 的本地条目键提供完整 XML，包含原生甘特图、引用和素材。')
            for xml in authored.values():validate_xml(xml)
            for item in local.values():
                if not is_fresh(db,pid,item['revision_id'],item['block_id']):raise YuError('COLLAB_REVIEW_PENDING','先更新受影响的策划文档。')
            # Each mapped section gets its own stable heading. Keep round/plan identity local.
            names={key:f'{local[key]["title"]} · {i+1}' for i,key in enumerate(local)}
            xml='<title>'+escape(app._project(pid)['name']+'｜项目创意协作文档')+'</title>'
            for key in local: xml+='<h1>'+escape(names[key])+'</h1>'+authored[key]
            written=remote_write(['+create'],xml);created=written['document'];url=valid_url(created['url'])
            # Persist the locator immediately; uncertain readback must never create another doc.
            db.execute('INSERT INTO collaboration_docs(project_id,url,created_at) VALUES(?,?,?)',(pid,url,now()))
            if written.get('warnings'):raise YuError('COLLAB_WRITE_UNCERTAIN','文档已创建并保留链接；请回读核对飞书写入警告。',details=written['warnings'])
            snapshot=fetch(url);heads={''.join(n.itertext()):n.get('id') for n in nodes(snapshot) if n.tag=='h1'}
            mappings={key:heads.get(name) for key,name in names.items()}
            if not all(mappings.values()):raise YuError('COLLAB_WRITE_UNCERTAIN','文档已创建，但章节映射需回读修复；保留原链接。')
            remote=sections(snapshot,mappings);base={'local':local,'remote':remote}
            db.execute('UPDATE collaboration_docs SET baseline_json=?,observed_json=?,mappings_json=?,last_synced_at=? WHERE project_id=?',(canonical(base),canonical(snapshot),canonical(mappings),now(),pid))
        else:
            url=valid_url(p.get('url'));snapshot=fetch(url);mappings=p.get('mappings',{})
            if not isinstance(mappings,dict) or not set(mappings)<=set(local) or any(not isinstance(v,str) for v in mappings.values()) or len(set(mappings.values()))!=len(mappings):raise YuError('INVALID_INPUT','映射必须使用本项目条目键及不同飞书块。')
            heads={n.get('id') for n in nodes(snapshot) if n.tag=='h1'}
            if not set(mappings.values())<=heads:raise YuError('INVALID_INPUT','映射必须指向一级标题。')
            remote=sections(snapshot,mappings)
            if any(not v for v in remote.values()):raise YuError('INVALID_INPUT','映射的飞书章节不存在。')
            # Binding an existing doc is an intake, never silently assume equality.
            db.execute('INSERT INTO collaboration_docs(project_id,url,mappings_json,created_at) VALUES(?,?,?,?)',(pid,url,canonical(mappings),now()))
            observe(app,pid)
        db.execute("UPDATE projects SET working_scene='review' WHERE id=?",(pid,))
        return public(db,pid)
    row=get(db,pid)
    if action in {'pause','resume'}:
        db.execute('UPDATE collaboration_docs SET enabled=?,version=version+1 WHERE project_id=?',(int(action=='resume'),pid));return public(db,pid)
    if not row['enabled']:raise YuError('COLLAB_PAUSED','协作同步已暂停。')
    if action=='map':
        snapshot=fetch(row['url']);local=local_sections(db,pid);mappings=p.get('mappings')
        if not isinstance(mappings,dict) or not set(mappings)<=set(local) or any(not isinstance(v,str) for v in mappings.values()) or len(set(mappings.values()))!=len(mappings):raise YuError('INVALID_INPUT','映射须为本项目内容键到不同飞书一级标题 ID。')
        heads={n.get('id') for n in nodes(snapshot) if n.tag=='h1'}
        if not set(mappings.values())<=heads:raise YuError('INVALID_INPUT','映射标题不存在。')
        db.execute('UPDATE collaboration_docs SET mappings_json=?,version=version+1 WHERE project_id=?',(canonical(mappings),pid))
        observe(app,pid)
        return public(db,pid)
    if action=='scheduler-bind':
        schedule=p.get('schedule',{})
        if not isinstance(schedule,dict) or any(not isinstance(schedule.get(k),str) or not schedule[k] for k in ['automation_id','thread_id','host_id']) or schedule.get('state') not in ['active','paused','error'] or type(schedule.get('interval_minutes')) is not int or schedule['interval_minutes']<1:raise YuError('INVALID_INPUT','需要实际宿主定时任务回执及真实间隔。')
        db.execute('UPDATE collaboration_docs SET schedule_json=?,version=version+1 WHERE project_id=?',(canonical({**schedule,'verified_at':now()}),pid));return public(db,pid)
    if action=='resolve':
        event=db.execute("SELECT * FROM collaboration_events WHERE project_id=? AND id=? AND state='conflict'",(pid,p.get('event_id'))).fetchone()
        if not event:raise YuError('INVALID_INPUT','未找到待处理冲突。')
        source=db.execute('SELECT 1 FROM source_versions WHERE project_id=? AND id=? AND sealed=1',(pid,p.get('instruction_source_version_id'))).fetchone()
        if not source or p.get('choice') not in ['local','remote','merge'] or not p.get('reason'):raise YuError('INVALID_INPUT','解决冲突需要用户选择及指令来源。')
        db.execute("UPDATE collaboration_events SET state='pending',resolution_json=? WHERE id=?",(canonical(p),event['id']));return {'event_id':event['id'],'resolved_choice':p['choice']}
    if action=='accept':
        observe(app,pid)
        row=get(db,pid)
        event=db.execute("SELECT * FROM collaboration_events WHERE project_id=? AND id=? AND state='pending'",(pid,p.get('event_id'))).fetchone()
        if not event:raise YuError('COLLAB_CONFLICT','变化仍有冲突，或已被其他执行者处理。')
        if not p.get('reason') or p.get('outcome') not in ['applied','no_business_change']:raise YuError('INVALID_INPUT','需要处理结果与具体理由。')
        ids=p.get('change_ids',[])
        if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids):raise YuError('INVALID_INPUT','change_ids 需要字符串列表。')
        if p['outcome']=='applied':
            valid=False
            for cid in ids:
                ch=db.execute("SELECT * FROM changes WHERE project_id=? AND id=? AND command='draft.apply' AND effect='changed'",(pid,cid)).fetchone()
                if ch:
                    refs=json.loads(ch['changed_refs_json'])
                    for ref in refs:
                        rid=ref.get('revision_id')
                        if rid and db.execute('SELECT 1 FROM revision_sources WHERE project_id=? AND revision_id=? AND source_version_id=?',(pid,rid,event['source_snapshot_id'])).fetchone():valid=True
            if not valid:raise YuError('DRAFT_CHANGE_REQUIRED','需先用该飞书变化作为依据更新 draft。')
        # Every current rendered review must be fresh; ordinary review.publish enforces causes.
        for entry in local_sections(db,pid).values():
            if not is_fresh(db,pid,entry['revision_id'],entry['block_id']):raise YuError('COLLAB_REVIEW_PENDING','相关策划文档尚未按最新 draft 更新。')
        snapshot=json.loads(event['snapshot_json']);observed=json.loads(row['observed_json'] or '{}')
        if snapshot!=observed:raise YuError('COLLAB_REMOTE_CHANGED','还有较新的变化，请合并处理最新快照。')
        local=local_sections(db,pid);remote=sections(snapshot,json.loads(row['mappings_json']));base=json.loads(row['baseline_json'])
        states=changes(base,local,remote)
        resolved=json.loads(event['resolution_json'] or '{}')
        affected={k for k,v in states.items() if v in {'remote','conflict'}}
        handled=p.get('handled_keys',[])
        if not isinstance(handled,list) or any(not isinstance(k,str) for k in handled) or set(handled)!=affected:raise YuError('INVALID_INPUT','handled_keys 必须逐项列出本次处理的所有远端变化章节。')
        if any(x['state']=='conflict' for x in read_pending(db,pid)):raise YuError('COLLAB_CONFLICT','还有未解决的多人修改冲突。')
        if p['outcome']=='no_business_change' and any(v in ['remote','conflict'] for v in states.values()):raise YuError('DRAFT_CHANGE_REQUIRED','正文变化需先写入 draft；纯排版请保存编写依据后更新 review。')
        for key,state in states.items():
            if state in ['remote','conflict']:
                if key in local:
                    entry=dict(local[key])
                    if resolved.get('choice') in {'local','merge'}:
                        # User selected a result that still needs remote publication.
                        entry['hash']='pending_remote_write'
                    base.setdefault('local',{})[key]=entry
                else:base.setdefault('local',{}).pop(key,None)
                base.setdefault('remote',{})[key]=remote.get(key)
        # New unmapped team contributions remain in the immutable source until mapped by Agent.
        # Accept records understanding of remote edits. No write-back is necessary unless requested later.
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute("UPDATE collaboration_events SET state='processed',resolution_json=? WHERE project_id=? AND created_at<=? AND state='pending'",(canonical({**p,'user_resolution':resolved}),pid,event['created_at']))
            db.execute('UPDATE collaboration_docs SET baseline_json=?,last_synced_at=?,version=version+1 WHERE project_id=?',(canonical(base),now(),pid));db.execute('COMMIT')
        except BaseException:db.execute('ROLLBACK');raise
        return public(db,pid)
    if action=='push':
        local=local_sections(db,pid);key=p.get('key');entry=local.get(key)
        if not entry or entry['revision_id']!=p.get('expected_local_revision'):raise YuError('BASE_REVISION_CONFLICT','本地策划文档已变化。')
        if not is_fresh(db,pid,entry['revision_id'],entry['block_id']):raise YuError('COLLAB_REVIEW_PENDING','先更新 draft 所影响的策划文档。')
        observed=observe(app,pid);snapshot=observed['snapshot']
        if snapshot['revision']!=p.get('base_revision'):raise YuError('COLLAB_REMOTE_CHANGED','飞书版本已变化，重新 pull 后合并，未回写。')
        mappings=json.loads(row['mappings_json']);remote=sections(snapshot,mappings);base=json.loads(row['baseline_json']);state=changes(base,local,remote).get(key)
        if state in ['remote','conflict']:raise YuError('COLLAB_CONFLICT','先吸收飞书变化或解决冲突，未回写。')
        xml=p.get('xml')
        validate_xml(xml)
        old=remote.get(key)
        if not old:
            if key in mappings:raise YuError('COLLAB_MAPPING_REQUIRED','原章节已被删除，请确认删减意图并修复映射。')
            title=entry['title']+' · '+entry['block_id']
            heading='<h1>'+escape(title)+'</h1>';group=[]
        else:
            group=nodes({'content':old['xml']});heading=normalized(ET.tostring(group[0],encoding='unicode'));title=''.join(group[0].itertext())
        # Replacing annotated blocks can detach discussion threads. Fail closed.
        refs=snapshot.get('reference_map') or {}
        if old and (re.search(r'<comment|comment[-_]id=',old['xml']) or any('comment' in str(k).lower() and v for k,v in refs.items())):
            raise YuError('COLLAB_COMMENT_PROTECTED','文档含协作评论，保留原块；请先处理评论并通过支持的原位编辑调整，不能替换整节。')
        # Do not replace resource-containing sections blindly; explicit XML must retain tokens.
        tokens=re.findall(r'(?:token|src)="([A-Za-z0-9_-]+)"',(old or {}).get('xml',''))
        if any(token not in xml for token in tokens):raise YuError('COLLAB_RESOURCE_LOSS','需保留原图片、画板与附件引用；请局部调整。')
        args=['+update','--doc',row['url'],'--revision-id',str(snapshot['revision'])]
        args+=['--command','block_replace','--start-block-id',old['start'],'--end-block-id',old['end']] if old else ['--command','append']
        written=remote_write(args,heading+xml)
        if written.get('warnings'):raise YuError('COLLAB_WRITE_UNCERTAIN','飞书写入返回警告，请回读核对后继续。',details=written['warnings'])
        after=fetch(row['url']);heads=[n for n in nodes(after) if n.tag=='h1' and ''.join(n.itertext())==title]
        if len(heads)!=1:raise YuError('COLLAB_WRITE_UNCERTAIN','写入后章节身份不明确，需回读修复。')
        mappings[key]=heads[0].get('id');newremote=sections(after,mappings)
        base.setdefault('local',{})[key]=entry;base.setdefault('remote',{})[key]=newremote[key]
        # Preserve other-section races as pending; only our verified section is acknowledged.
        expected_text=''.join(ET.fromstring('<root>'+heading+xml+'</root>').itertext())
        actual_text=''.join(ET.fromstring('<root>'+newremote[key]['xml']+'</root>').itertext())
        if re.sub(r'\s+','',expected_text)!=re.sub(r'\s+','',actual_text):
            observe(app,pid)
            raise YuError('COLLAB_WRITE_UNCERTAIN','回读内容与提交不一致，保留双方内容，请重新核对。')
        def remainder(snap,section):
            ids=set(n.get('id') for n in nodes({'content':section['xml']})) if section else set()
            return normalized(''.join(ET.tostring(n,encoding='unicode') for n in nodes(snap) if n.get('id') not in ids))
        unchanged=remainder(snapshot,old)==remainder(after,newremote[key]) and snapshot.get('reference_map')==after.get('reference_map')
        db.execute('UPDATE collaboration_docs SET baseline_json=?,mappings_json=?,observed_json=?,last_synced_at=?,version=version+1 WHERE project_id=?',(canonical(base),canonical(mappings),canonical(after if unchanged else snapshot),now(),pid))
        if not unchanged:observe(app,pid)
        return public(db,pid)
    raise YuError('INVALID_INPUT','无效协作操作。')


def poll(data_dir,stop):
    from .app import App
    while not stop.is_set():
        app=App(data_dir)
        try:
            pids=[r[0] for r in app.db.execute("SELECT c.project_id FROM collaboration_docs c JOIN projects p ON p.id=c.project_id WHERE c.enabled=1 AND p.lifecycle='active'")]
            for pid in pids:
                if stop.is_set():break
                try:
                    with lock(app,pid):observe(app,pid)
                except (YuError,OSError,ValueError) as exc:
                    app.db.execute('UPDATE collaboration_docs SET error_json=?,last_checked_at=? WHERE project_id=?',(canonical({'message':str(exc),'at':now()}),now(),pid))
        finally:app.close()
        stop.wait(60)
