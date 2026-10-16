"""Command boundary: validate, replay, transact, and return stable receipts."""
from __future__ import annotations
from contextlib import contextmanager
import json
import base64
from pathlib import Path
import re
import sqlite3
from jsonschema import Draft202012Validator, FormatChecker
from .core import Context, YuError, canonical, digest, new_id, now, insert, get_object, load_revision, affected_objects

CONTRACTS=Path(__file__).parent/'contracts'
CORE_COMMANDS={'source.import','draft.apply','review.prepare','review.publish'}
WRITE_COMMANDS={'project.create','source.import','draft.apply','review.publish'}
ID_PATTERN=re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,127}$')

class App:
    def __init__(self,data_dir):
        if sqlite3.sqlite_version_info<(3,51,3):
            raise YuError('RUNTIME_UNSUPPORTED','需要 SQLite >=3.51.3；请使用带有此版本的 Python 运行环境。',details=[{'sqlite_version':sqlite3.sqlite_version}])
        self.data_dir=Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.data_dir/'yuplus.sqlite',isolation_level=None,timeout=5)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA recursive_triggers=ON')
        self.db.execute('PRAGMA busy_timeout=5000');self.db.execute('PRAGMA synchronous=FULL')
        mode=self.db.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        if mode!='wal':raise YuError('INTEGRITY_FAILURE','无法启用 SQLite WAL。')
        self._initialize()
        schema=json.loads((CONTRACTS/'cli-input.schema.json').read_text())
        self.validator=Draft202012Validator(schema,format_checker=FormatChecker())
    def close(self): self.db.close()
    def _initialize(self):
        # executescript commits any pending transaction, so put BEGIN in the script.
        # Concurrent starters serialize on BEGIN and re-check user_version afterwards.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            version=self.db.execute('PRAGMA user_version').fetchone()[0]
            if version==0:
                existing=self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                if existing: raise YuError('INTEGRITY_FAILURE','未识别的数据库，拒绝覆盖。')
                script=(CONTRACTS/'schema.sql').read_text()
                # Execute complete statements individually without executescript's implicit commit.
                pending=''
                for line in script.splitlines(keepends=True):
                    pending+=line
                    if sqlite3.complete_statement(pending):
                        self.db.execute(pending);pending=''
                if pending.strip() and not all(x.strip().startswith('--') or not x.strip() for x in pending.splitlines()):
                    raise YuError('INTEGRITY_FAILURE','Schema 文件不完整。')
            elif version!=1: raise YuError('INTEGRITY_FAILURE','数据库版本不兼容，拒绝修改。')
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def _project(self,pid,write=False):
        if not pid:raise YuError('INVALID_INPUT','必须显式指定 --project。')
        row=self.db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not row: raise YuError('PROJECT_NOT_FOUND','项目不存在。')
        if write and row['lifecycle']=='archived':raise YuError('PROJECT_ARCHIVED','项目已归档。')
        return dict(row)
    def cursor(self,pid):
        return self.db.execute('SELECT COALESCE(MAX(seq),0) FROM changes WHERE project_id=?',(pid,)).fetchone()[0] if pid else 0
    def _envelope(self,command,pid,request,data,change=None,cursor=None,replayed=False):
        return {'api_version':'1','command':command,'ok':True,'project_id':pid,'request_id':request,'data':data,
                'meta':{'change_id':change,'history_cursor':self.cursor(pid) if cursor is None else cursor,'replayed':replayed}}
    def _validate(self,command,payload,request_id):
        if not isinstance(payload,dict):raise YuError('INVALID_INPUT','输入必须是 JSON 对象。')
        if command in WRITE_COMMANDS and (not isinstance(request_id,str) or not ID_PATTERN.fullmatch(request_id)):
            raise YuError('INVALID_INPUT','写命令需要合法的 --request-id。')
        if command in CORE_COMMANDS:
            if payload.get('command')!=command:raise YuError('INVALID_INPUT','输入 command 与命令行不一致。')
            errors=list(self.validator.iter_errors(payload))
            if errors:
                # Root oneOf messages include the whole request; report leaf locations instead.
                leaves=[]
                def collect(error):
                    if error.context:
                        for sub in error.context:collect(sub)
                    else:leaves.append(error)
                for err in errors:collect(err)
                relevant=[err for err in leaves if list(err.absolute_path)!=['command']]
                details=[{'path':'/'+ '/'.join(map(str,e.absolute_path)),'message':e.message[:300]} for e in relevant[:10]]
                raise YuError('INVALID_INPUT','输入不符合命令 Schema。',details=details)
        elif command=='project.create':
            if set(payload)-{'name','api_version','command'} or not isinstance(payload.get('name'),str) or not payload['name'].strip():
                raise YuError('INVALID_INPUT','项目名称不能为空，且不能包含未知字段。')
        try: serialized=canonical(payload).encode('utf-8')
        except (ValueError,TypeError,UnicodeError) as exc: raise YuError('INVALID_INPUT','JSON 包含不支持的值。') from exc
        if len(serialized)>8*1024*1024:raise YuError('INPUT_TOO_LARGE','单次 JSON 不能超过 8 MiB。')
        if command=='draft.apply' and (len(payload['objects'])>100 or sum(len(o.get('set_items',[]))+len(o.get('remove_items',[])) for o in payload['objects'])>1000):
            raise YuError('INPUT_TOO_LARGE','单次最多 100 个对象操作及 1000 个条目变动。')
    def _replay(self,command,pid,request_id,request_hash):
        if command=='project.create':
            row=self.db.execute("SELECT * FROM changes WHERE command='project.create' AND request_id=?",(request_id,)).fetchone()
        else: row=self.db.execute('SELECT * FROM changes WHERE project_id=? AND request_id=?',(pid,request_id)).fetchone()
        if row:
            if row['request_hash']!=request_hash:raise YuError('IDEMPOTENCY_CONFLICT','同一 request-id 已用于不同请求。')
            return self._envelope(command,row['project_id'],request_id,json.loads(row['result_json']),row['id'],row['seq'],True)
        return None
    def execute(self,command,payload=None,*,project_id=None,request_id=None):
        payload={} if payload is None else payload
        self._validate(command,payload,request_id)
        if command not in WRITE_COMMANDS:
            self.db.execute('BEGIN')
            try:
                data=self._read(command,payload,project_id)
                result=self._envelope(command,project_id,None,data)
                self.db.execute('COMMIT');return result
            except BaseException:self.db.execute('ROLLBACK');raise
        request_hash=digest({'api_version':'1','command':command,'project_id':project_id,'input':payload})
        replay=self._replay(command,project_id,request_id,request_hash)
        if replay:return replay
        if command!='project.create':self._project(project_id,True)
        prepared=None
        if command=='source.import':
            from .source import prepare_import
            prepared=prepare_import(self.data_dir,payload)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            replay=self._replay(command,project_id,request_id,request_hash)
            if replay:self.db.execute('COMMIT');return replay
            cid=new_id('chg')
            if command=='project.create':
                if project_id is not None:raise YuError('INVALID_INPUT','创建项目不接受已有 --project。')
                project_id=new_id('prj');t=now()
                insert(self.db,'projects',id=project_id,name=payload['name'].strip(),created_at=t,updated_at=t)
                ctx=Context(self.db,self.data_dir,project_id,cid)
                ctx.changed_refs.append({'project_id':project_id})
                data={'effect':'changed','project_id':project_id,'name':payload['name'].strip(),'metadata_version':1,'working_scene':'draft','lifecycle':'active'}
            else:
                self._project(project_id,True);ctx=Context(self.db,self.data_dir,project_id,cid)
                if command=='source.import':
                    from .source import import_source
                    data=import_source(ctx,payload,prepared)
                elif command=='draft.apply':
                    from .draft import apply_draft
                    data=apply_draft(ctx,payload)
                else:
                    from .review import publish_review
                    data=publish_review(ctx,payload)
            for table in ('source_versions','object_revisions'):
                if self.db.execute(f'SELECT 1 FROM {table} WHERE project_id=? AND change_id=? AND sealed=0',(project_id,cid)).fetchone():
                    raise YuError('INTEGRITY_FAILURE','提交包含未封存版本。')
            insert(self.db,'changes',id=cid,project_id=project_id,command=command,effect=data.get('effect','changed'),request_id=request_id,request_hash=request_hash,
                   actor_json=canonical({'kind':'cli'}),reason=payload.get('reason','创建项目'),causal_change_ids_json=canonical(sorted(set(ctx.causal_change_ids))),
                   changed_refs_json=canonical(ctx.changed_refs),result_json=canonical(data),created_at=now())
            seq=self.db.execute('SELECT seq FROM changes WHERE id=?',(cid,)).fetchone()[0]
            self.db.execute('COMMIT')
            return self._envelope(command,project_id,request_id,data,cid,seq)
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def _page_position(self, command, pid, value):
        if type(value) is int and value >= 0:return value, ''
        if isinstance(value,str) and value.isdecimal():return int(value), ''
        if not isinstance(value,str) or len(value)>4096:raise YuError('INVALID_INPUT','分页游标不合法。')
        try:
            data=json.loads(base64.urlsafe_b64decode(value.encode('ascii')))
            if set(data)!={'v','project_id','command','seq','id'} or data['v']!=1 or data['project_id']!=pid or data['command']!=command or type(data['seq']) is not int or data['seq']<0 or not isinstance(data['id'],str) or not ID_PATTERN.fullmatch(data['id']):raise ValueError()
            return data['seq'],data['id']
        except (ValueError,TypeError,KeyError,UnicodeError) as exc:raise YuError('INVALID_INPUT','分页游标无效或不属于当前查询。') from exc
    def _page_cursor(self, command, pid, seq, ident):
        return base64.urlsafe_b64encode(canonical({'v':1,'project_id':pid,'command':command,'seq':seq,'id':ident}).encode()).decode()
    def _read(self,command,payload,pid):
        if command=='project.list':
            return {'projects':[{'project_id':r['id'],**{k:r[k] for k in ('name','working_scene','lifecycle','metadata_version')}} for r in self.db.execute('SELECT * FROM projects ORDER BY created_at,id')]}
        if command=='doctor':
            return {'sqlite_version':sqlite3.sqlite_version,'data_dir':str(self.data_dir),'schema_version':1,'journal_mode':'wal'}
        if command=='types.show':
            data=json.loads((CONTRACTS/'object-types.json').read_text());key=payload.get('type_key')
            if key:
                items=[i for i in data['objects']+data['internal_types'] if i['type_key']==key]
                if not items:raise YuError('OBJECT_NOT_FOUND','未知对象类型。')
                return {'type':items[0]}
            return data
        self._project(pid)
        if command=='project.show':return {'project_id':pid,**self._project(pid)}
        if command=='review.prepare':
            from .review import prepare_review
            return prepare_review(Context(self.db,self.data_dir,pid,None),payload)
        if command=='source.show':
            from .source import show_source
            result=show_source(self.db,pid,payload['source_id'],payload.get('snapshot_id'),self.data_dir)
            if result['snapshot'] is not None:
                omitted=result['snapshot']['body'] is not None and not payload.get('include_body',False)
                result['snapshot']['body_omitted']=omitted
                if omitted:result['snapshot']['body']=None
            return result
        if command=='source.list':
            from .browser_view import decoded
            return {'sources':[decoded(r) for r in self.db.execute('SELECT id,provider,cached_title,canonical_url,latest_snapshot_id,remote_observation_json,check_error_json,last_checked_at FROM sources WHERE project_id=? ORDER BY created_at,id',(pid,))]}
        if command in {'draft.list','review.list'}:
            layer=command.split('.')[0]
            return {'objects':[dict(r) for r in self.db.execute('SELECT id,type_key,scope_key,current_revision_id FROM objects WHERE project_id=? AND layer=? AND archived_at IS NULL ORDER BY created_at,id',(pid,layer))]}
        if command in {'draft.show','review.show'}:
            o=get_object(self.db,pid,payload['object_id'])
            if o['layer']!=command.split('.')[0]:raise YuError('INVALID_INPUT','对象层与命令不一致。')
            rid=payload.get('revision_id') or o['current_revision_id'];r=load_revision(self.db,pid,rid)
            if r['object_id']!=o['id']:raise YuError('INVALID_ITEM_REFERENCE','版本不属于指定对象。')
            result={'object_id':o['id'],'type_key':o['type_key'],'revision_id':rid,'version':r['version'],**r['payload'],'sources':r['sources'],'dependencies':r['dependencies'],'lineage':r['lineage']}
            if command=='review.show':result['affected']=next((v['block_ids'] for v in affected_objects(self.db,pid)['review'] if v['object_id']==o['id']),[])
            return result
        if command in {'changes.list','decisions.list'}:
            limit=payload.get('limit',50)
            if type(limit) is not int or not 1<=limit<=200:raise YuError('INVALID_INPUT','分页参数不合法。')
            after,last_id=self._page_position(command,pid,payload.get('after_cursor',0))
            if command=='changes.list':
                rows=self.db.execute("SELECT * FROM changes WHERE project_id=? AND seq>? AND effect='changed' ORDER BY seq LIMIT ?",(pid,after,limit+1)).fetchall()
                data=[dict(r) for r in rows[:limit]]
                for d in data:
                    for k in ('changed_refs_json','causal_change_ids_json','actor_json','result_json'):d[k.removesuffix('_json')]=json.loads(d.pop(k))
                    d.pop('request_hash')
                return {'changes':data,'has_more':len(rows)>limit,'next_cursor':self._page_cursor(command,pid,data[-1]['seq'],data[-1]['id']) if len(rows)>limit else None}
            rows=self.db.execute('SELECT d.*,c.seq AS change_seq FROM decisions d JOIN changes c ON c.id=d.change_id WHERE d.project_id=? AND (c.seq>? OR (c.seq=? AND d.id>? AND ?<>\'\')) ORDER BY c.seq,d.id LIMIT ?',(pid,after,after,last_id,last_id,limit+1)).fetchall()
            data=[dict(r) for r in rows[:limit]]
            for d in data:d['affected_refs']=json.loads(d.pop('affected_refs_json'))
            return {'decisions':data,'has_more':len(rows)>limit,'next_cursor':self._page_cursor(command,pid,data[-1]['change_seq'],data[-1]['id']) if len(rows)>limit else None}
        raise YuError('INVALID_INPUT','不支持的命令。',details=[{'command':command}])
