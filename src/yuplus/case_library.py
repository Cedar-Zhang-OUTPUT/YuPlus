"""Workspace-wide source registry; contents stay remote and are read on demand."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from .core import YuError, canonical, digest, new_id, now

ACTIONS={'add','list','show','update','delete','restore'}
POLICY={'storage':'source_metadata_only','lookup':'on_demand_by_kind','deletion':'local_registration_only'}

def envelope(app,*args,**kwargs):
    result=app._envelope(*args,**kwargs)
    result['meta']['library_policy']=dict(POLICY)
    return result

def folder_url(value):
    if not isinstance(value,str) or len(value)>4096 or any(ord(c)<32 for c in value) or '\\' in value:
        raise YuError('INVALID_INPUT','请提供飞书共享文件夹链接。')
    value=value.strip()
    try:
        url=urlsplit(value)
        host=(url.hostname or '').lower()
        valid_host=any(host==d or host.endswith('.'+d) for d in ('feishu.cn','larksuite.com'))
        match=re.fullmatch(r'/(?:drive/)?folder/([A-Za-z0-9_-]+)/*',url.path)
        if url.scheme!='https' or not valid_host or url.username or url.password or url.port not in (None,443) or not match:
            raise ValueError()
    except ValueError:
        raise YuError('INVALID_INPUT','需要 https 飞书共享文件夹链接（/drive/folder/…），不能是文档或群聊链接。') from None
    return f'https://{host}/drive/folder/{match[1]}'

def website_url(value):
    if not isinstance(value,str) or len(value)>4096 or any(ord(c)<32 for c in value) or '\\' in value:
        raise YuError('INVALID_INPUT','请提供 http 或 https 网站链接。')
    try:
        url=urlsplit(value.strip())
        host=(url.hostname or '').encode('idna').decode('ascii').lower()
        if url.scheme not in ('http','https') or not host or re.search(r'\s|[%/?#]',host) or url.username is not None or url.password is not None:
            raise ValueError()
        port=url.port
        if ':' in host:host='['+host+']'
        if port is not None and port != (443 if url.scheme=='https' else 80):host+=':'+str(port)
        from urllib.parse import urlunsplit, quote
        return urlunsplit((url.scheme,host,quote(url.path or '/',safe="/%:@!$&'()*+,;=-._~"),quote(url.query,safe="/%?:@!$&'()*+,;=-._~"),quote(url.fragment,safe="/%?:@!$&'()*+,;=-._~")))
    except (ValueError,UnicodeError):
        raise YuError('INVALID_INPUT','需要有效的 http 或 https 网站链接，不能包含登录凭据。') from None

def source_url(value,kind):
    if kind=='feishu_folder':return folder_url(value)
    if kind=='website':return website_url(value)
    raise YuError('INVALID_INPUT','kind 必须为 feishu_folder 或 website。')


# Reserved prefix cannot collide with public CLI request IDs. The receipt travels
# with database backups, so removed or edited defaults stay that way on restore.
_LEGACY_RECEIPT = '__builtin_case_libraries_v1'
_DEFAULT_RECEIPT = '__builtin_case_libraries_v2'
_DEFAULTS = Path(__file__).parent/'contracts'/'default-case-libraries.json'


def initialize_defaults(db):
    """Called inside App's initialization transaction, once per workspace."""
    if db.execute('SELECT 1 FROM case_library_requests WHERE request_id=?', (_DEFAULT_RECEIPT,)).fetchone():
        return
    entries = json.loads(_DEFAULTS.read_text())['libraries']
    # v1 already installed the first 18 sources. Only seed the new batch on
    # upgrade, even if a user edited, disabled or purged an older source.
    if db.execute('SELECT 1 FROM case_library_requests WHERE request_id=?', (_LEGACY_RECEIPT,)).fetchone():
        entries = entries[18:]
    stamp = now()
    added, reused = [], []
    for entry in entries:
        kind, name = entry['kind'], entry['name']
        if not isinstance(name,str) or not name.strip() or len(name)>200:
            raise YuError('INVALID_INPUT','内置案例库名称无效。')
        url = source_url(entry['url'],kind)
        # Include removed registrations: initialization must never undo removal.
        row = db.execute('SELECT id FROM case_libraries WHERE url=?',(url,)).fetchone()
        if row:
            reused.append(row['id'])
            continue
        identity = new_id('lib')
        db.execute('INSERT INTO case_libraries(id,name,url,kind,version,created_at,updated_at) VALUES(?,?,?,?,1,?,?)',
                   (identity,name.strip(),url,kind,stamp,stamp))
        added.append(identity)
    db.execute('INSERT INTO case_library_requests VALUES(?,?,?,?,?)',
               (_DEFAULT_RECEIPT,digest(entries),'library.initialize',canonical({'added':added,'reused':reused}),stamp))


def listed(db,include_deleted=False):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='case_libraries'").fetchone():return []
    return [dict(r) for r in db.execute('SELECT * FROM case_libraries'+('' if include_deleted else ' WHERE deleted_at IS NULL')+' ORDER BY created_at DESC,id')]


def catalog(db):
    """Browser catalog includes disabled sources; CLI list remains enabled-only.

    Seed receipts keep Official provenance stable across renames and URL edits.
    No schema change or mutable client-supplied provenance is needed.
    """
    official = set()
    for row in db.execute('SELECT result_json FROM case_library_requests WHERE request_id IN (?,?)',
                          (_LEGACY_RECEIPT, _DEFAULT_RECEIPT)):
        receipt = json.loads(row['result_json'])
        official.update(receipt.get('added', []))
        official.update(receipt.get('reused', []))
    metadata = {source_url(e['url'], e['kind']): e for e in json.loads(_DEFAULTS.read_text())['libraries']}
    return [{**row, 'origin': 'official' if row['id'] in official else 'personal',
             'enabled': row['deleted_at'] is None,
             'logo': metadata.get(row['url'], {}).get('logo'),
             'description': metadata.get(row['url'], {}).get('description', ''),
             'category': metadata.get(row['url'], {}).get('category', '其他来源')}
            for row in listed(db, include_deleted=True)]

def execute(app,command,payload,project_id,request_id):
    action=command.split('.')[1]
    if action not in ACTIONS or project_id is not None:raise YuError('INVALID_INPUT','案例库属于工作空间，不接受 --project。')
    if not isinstance(payload,dict):raise YuError('INVALID_INPUT','输入必须是对象。')
    if action=='list':
        if set(payload)-{'include_deleted'} or type(payload.get('include_deleted',False)) is not bool:raise YuError('INVALID_INPUT','无效列表参数。')
        return envelope(app,command,None,None,{'libraries':listed(app.db,payload.get('include_deleted',False))})
    allowed={'library_id'} if action=='show' else {'api_version','command','library_id','base_version'}
    if action in ('add','update'):allowed|={'name','url','kind'}
    if action=='add':allowed-={'library_id','base_version'}
    if set(payload)-allowed:raise YuError('INVALID_INPUT','案例库只登记类型、名称和链接及管理元数据，不接收正文、附件、目录清单或内容索引。')
    if action!='show':
        if payload.get('api_version')!='1' or payload.get('command')!=command:raise YuError('INVALID_INPUT','需要 api_version: 1 和匹配的 command。')
        if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}',request_id):raise YuError('INVALID_INPUT','写操作需要合法 --request-id。')
    if action!='add' and (not isinstance(payload.get('library_id'),str) or not payload['library_id']):raise YuError('INVALID_INPUT','需要 library_id。')
    if action not in ('add','show') and (type(payload.get('base_version')) is not int or payload['base_version']<1):raise YuError('INVALID_INPUT','需要当前 base_version。')
    name=url=None
    if action in ('add','update'):
        name=payload.get('name')
        if not isinstance(name,str) or not name.strip() or len(name)>200:raise YuError('INVALID_INPUT','案例库名称不能为空，最多 200 字。')
        name=name.strip()
    fingerprint=digest({'command':command,'input':payload})
    app.db.execute('BEGIN' if action=='show' else 'BEGIN IMMEDIATE')
    try:
        if action!='show':
            receipt=app.db.execute('SELECT * FROM case_library_requests WHERE request_id=?',(request_id,)).fetchone()
            if receipt:
                if receipt['request_hash']!=fingerprint:raise YuError('IDEMPOTENCY_CONFLICT','该 request-id 已用于其他案例库请求。')
                app.db.execute('COMMIT')
                return envelope(app,command,None,request_id,json.loads(receipt['result_json']),replayed=True)
        row=None
        if action!='add':
            row=app.db.execute('SELECT * FROM case_libraries WHERE id=?',(payload['library_id'],)).fetchone()
            if not row:raise YuError('NOT_FOUND','案例库不存在。')
        if action=='show':
            app.db.execute('COMMIT');return envelope(app,command,None,None,dict(row))
        if row and row['version']!=payload['base_version']:raise YuError('VERSION_CONFLICT','案例库已变化，请重新读取。')
        if row and row['deleted_at'] and action!='restore':raise YuError('INVALID_INPUT','案例库已移除，请先恢复。')
        if row and not row['deleted_at'] and action=='restore':raise YuError('INVALID_INPUT','案例库未被移除。')
        kind=payload.get('kind',row['kind'] if row else 'feishu_folder')
        if action in ('add','update'):url=source_url(payload.get('url'),kind)
        identity=row['id'] if row else new_id('lib')
        stamp=now()
        if action in ('add','update'):
            duplicate=app.db.execute('SELECT id,deleted_at FROM case_libraries WHERE url=? AND id<>?',(url,identity)).fetchone()
            if duplicate:raise YuError('ALREADY_EXISTS','该链接已保存；已移除的记录可恢复。',details=[dict(duplicate)])
        if action=='add':
            app.db.execute('INSERT INTO case_libraries(id,name,url,kind,version,created_at,updated_at) VALUES(?,?,?,?,1,?,?)',(identity,name,url,kind,stamp,stamp))
        elif action=='update':
            app.db.execute('UPDATE case_libraries SET name=?,url=?,kind=?,version=version+1,updated_at=? WHERE id=?',(name,url,kind,stamp,identity))
        else:
            app.db.execute('UPDATE case_libraries SET deleted_at=?,version=version+1,updated_at=? WHERE id=?',(stamp if action=='delete' else None,stamp,identity))
        result=dict(app.db.execute('SELECT * FROM case_libraries WHERE id=?',(identity,)).fetchone())
        app.db.execute('INSERT INTO case_library_requests VALUES(?,?,?,?,?)',(request_id,fingerprint,command,canonical(result),stamp))
        app.db.execute('COMMIT');return envelope(app,command,None,request_id,result)
    except BaseException:
        app.db.execute('ROLLBACK');raise
