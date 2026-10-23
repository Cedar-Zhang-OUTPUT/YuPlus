"""Independent research rounds. Only locators and receipts are durable locally."""
import json
import re
from urllib.parse import urlsplit
from .core import YuError, canonical, digest, new_id, now

ACTIONS = {'create', 'update', 'list', 'show', 'preview'}


def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS case_research (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        version INTEGER NOT NULL CHECK(version>0), metadata_version INTEGER NOT NULL DEFAULT 1,
        title TEXT NOT NULL, document_url TEXT, board_url TEXT, board_token TEXT UNIQUE,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(project_id,version))''')
    db.execute('''CREATE TABLE IF NOT EXISTS case_research_requests (
        project_id TEXT NOT NULL REFERENCES projects(id), request_id TEXT NOT NULL,
        request_hash TEXT NOT NULL, result_json TEXT NOT NULL,
        PRIMARY KEY(project_id,request_id))''')
    db.execute('PRAGMA user_version=7')


def listed(db, pid):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='case_research'").fetchone(): return []
    return [dict(r) for r in db.execute('SELECT * FROM case_research WHERE project_id=? ORDER BY version DESC', (pid,))]


def get(db, pid, rid):
    row = db.execute('SELECT * FROM case_research WHERE project_id=? AND id=?', (pid, rid)).fetchone()
    if not row: raise YuError('RESEARCH_NOT_FOUND', '找案例研究不存在或不属于该项目。')
    return dict(row)


def locator(doc, board, token):
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,199}',token):
        raise YuError('INVALID_INPUT', '需要有效的飞书 board_token。')
    parsed=[]
    for value in (doc, board):
        if not isinstance(value,str) or len(value)>4096 or re.search(r'[\x00-\x20\\]',value):
            raise YuError('INVALID_INPUT','需要飞书文档及画板定位链接。')
        try:
            url=urlsplit(value); host=(url.hostname or '').lower()
            if url.scheme!='https' or url.username or url.password or url.port not in (None,443) or not any(host==d or host.endswith('.'+d) for d in ('feishu.cn','larksuite.com')) or not re.fullmatch(r'/docx/[A-Za-z0-9_-]+',url.path): raise ValueError()
            parsed.append(url)
        except ValueError: raise YuError('INVALID_INPUT','画板须使用飞书 docx 文档内的定位链接。') from None
    if parsed[0].netloc!=parsed[1].netloc or parsed[0].path!=parsed[1].path or not parsed[1].fragment:
        raise YuError('INVALID_INPUT','画板定位链接须指向同一文档，且包含画板块锚点。')


def execute(app, command, payload, pid, request):
    action=command.split('.')[1]
    if action not in ACTIONS or not isinstance(payload,dict): raise YuError('INVALID_INPUT','无效研究请求。')
    write=action in {'create','update'}
    app._project(pid,write=write or action=='preview')  # Archived history stays readable; no remote refresh.
    allowed={'research_id'} if action in {'show','preview'} else set()
    if write:
        allowed={'api_version','command','title'}
        if action=='update': allowed|={'research_id','base_version','document_url','board_url','board_token'}
    if set(payload)-allowed: raise YuError('INVALID_INPUT','研究只保存标题、版本及飞书定位，不接收案例正文或长期偏好。')
    if action in {'show','preview','update'} and not isinstance(payload.get('research_id'),str): raise YuError('INVALID_INPUT','需要 research_id / --research。')
    if action=='list': return app._envelope(command,pid,None,{'research':listed(app.db,pid)})
    if action=='show': return app._envelope(command,pid,None,get(app.db,pid,payload['research_id']))
    if action=='preview':
        from .case_preview import PreviewCache
        return app._envelope(command,pid,None,PreviewCache(app.data_dir).refresh(get(app.db,pid,payload['research_id'])))
    if payload.get('api_version')!='1' or payload.get('command')!=command or not isinstance(request,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}',request):
        raise YuError('INVALID_INPUT','写操作需要 api_version、匹配的 command 和合法 request-id。')
    if action=='create' or 'title' in payload:
        title=payload.get('title')
        if not isinstance(title,str) or not title.strip() or len(title)>200: raise YuError('INVALID_INPUT','研究标题需要 1–200 字。')
    if action=='update' and (type(payload.get('base_version')) is not int or payload['base_version']<1): raise YuError('INVALID_INPUT','base_version 使用最新 metadata_version。')
    keys={'document_url','board_url','board_token'}
    if keys & payload.keys():
        if not keys <= payload.keys(): raise YuError('INVALID_INPUT','画板关联需同时提供 document_url、board_url、board_token。')
        locator(payload['document_url'],payload['board_url'],payload['board_token'])
    fingerprint=digest({'command':command,'input':payload})
    app.db.execute('BEGIN IMMEDIATE')
    try:
        app._project(pid,write=True)
        receipt=app.db.execute('SELECT * FROM case_research_requests WHERE project_id=? AND request_id=?',(pid,request)).fetchone()
        if receipt:
            if receipt['request_hash']!=fingerprint: raise YuError('IDEMPOTENCY_CONFLICT','该 request-id 已用于其他研究请求。')
            app.db.execute('COMMIT')
            return app._envelope(command,pid,request,json.loads(receipt['result_json']),replayed=True)
        stamp=now()
        if action=='create':
            rid=new_id('research')
            version=app.db.execute('SELECT COALESCE(MAX(version),0)+1 FROM case_research WHERE project_id=?',(pid,)).fetchone()[0]
            app.db.execute('INSERT INTO case_research(id,project_id,version,title,created_at,updated_at) VALUES(?,?,?,?,?,?)',(rid,pid,version,payload['title'].strip(),stamp,stamp))
        else:
            rid=payload['research_id']; row=get(app.db,pid,rid)
            if row['metadata_version']!=payload['base_version']: raise YuError('VERSION_CONFLICT','研究记录已变化，请重新读取。')
            if keys <= payload.keys():
                if row['board_token'] and any(payload[k]!=row[k] for k in keys): raise YuError('INVALID_INPUT','已关联的画板不能替换；同轮修改原画板，新研究使用新画板。')
                duplicate=app.db.execute('SELECT id FROM case_research WHERE board_token=? AND id<>?',(payload['board_token'],rid)).fetchone()
                if duplicate: raise YuError('ALREADY_EXISTS','该画板已属于其他研究，不能用同一画板覆盖版本历史。')
            values={k:payload.get(k,row[k]) for k in keys}
            app.db.execute('UPDATE case_research SET title=?,document_url=?,board_url=?,board_token=?,metadata_version=metadata_version+1,updated_at=? WHERE id=?',
                (payload.get('title',row['title']).strip(),values['document_url'],values['board_url'],values['board_token'],stamp,rid))
        result=get(app.db,pid,rid)
        app.db.execute('INSERT INTO case_research_requests VALUES(?,?,?,?)',(pid,request,fingerprint,canonical(result)))
        app.db.execute('COMMIT')
        return app._envelope(command,pid,request,result)
    except BaseException:
        app.db.execute('ROLLBACK'); raise
