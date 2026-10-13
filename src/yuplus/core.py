"""Immutable revision primitives shared by the CLI domain modules."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

class YuError(Exception):
    def __init__(self, code, message, *, details=None, retryable=False, next_action=''):
        super().__init__(message)
        self.code, self.message = code, message
        self.details, self.retryable, self.next_action = details or [], retryable, next_action
    @property
    def exit_code(self):
        if self.code in {'INVALID_INPUT','UNKNOWN_FIELD','INPUT_TOO_LARGE'}: return 2
        if self.code.endswith('_NOT_FOUND') and self.code != 'FILE_NOT_FOUND': return 3
        if self.code in {'BASE_REVISION_CONFLICT','DRAFT_BASIS_CHANGED','IDEMPOTENCY_CONFLICT','SOURCE_EXISTS','SOURCE_DUPLICATE','SOURCE_REVISION_CONFLICT','SOURCE_REVISION_OUTDATED'}: return 4
        if self.code in {'FEISHU_UNAVAILABLE','SOURCE_CHECK_UNSUPPORTED','RUNTIME_UNSUPPORTED'}: return 6
        if self.code in {'FILE_NOT_FOUND','FILE_HASH_MISMATCH','IO_FAILURE','DISK_FULL'}: return 7
        if self.code == 'DATABASE_BUSY': return 8
        if self.code in {'INTERNAL_ERROR','INTEGRITY_FAILURE'}: return 70
        return 5

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()

def new_id(prefix): return prefix + '_' + uuid.uuid4().hex

def now(): return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')

def insert(db, table, **values):
    db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))

@dataclass
class Context:
    db: sqlite3.Connection
    data_dir: Path
    project_id: str
    change_id: str | None
    changed_refs: list = field(default_factory=list)
    causal_change_ids: list = field(default_factory=list)

def scoped_row(db, table, project_id, ident, code):
    row=db.execute(f'SELECT * FROM {table} WHERE project_id=? AND id=?',(project_id,ident)).fetchone()
    if row is None:
        if db.execute(f'SELECT 1 FROM {table} WHERE id=?',(ident,)).fetchone():
            raise YuError('CROSS_PROJECT_REFERENCE','引用不属于当前项目。')
        raise YuError(code,'引用不存在。',details=[{'id':ident}])
    return dict(row)

def get_object(db, project_id, object_id):
    return scoped_row(db,'objects',project_id,object_id,'OBJECT_NOT_FOUND')

def load_revision(db, project_id, revision_id):
    row=scoped_row(db,'object_revisions',project_id,revision_id,'REVISION_NOT_FOUND')
    if not row['sealed']: raise YuError('INTEGRITY_FAILURE','不能读取未封存的版本。')
    row['payload']=json.loads(row['payload_json']); row['lineage']=json.loads(row['block_lineage_json'])
    row['sources']={}; row['dependencies']={}
    for r in db.execute('SELECT * FROM revision_sources WHERE project_id=? AND revision_id=? ORDER BY item_id,evidence_id',(project_id,revision_id)):
        value={'evidence_id':r['evidence_id'],'source_version_id':r['source_version_id'],'locator':json.loads(r['locator_json']),'kind':r['evidence_kind']}
        if r['asset_id'] is not None: value['asset_id']=r['asset_id']
        row['sources'].setdefault(r['item_id'],[]).append(value)
    for r in db.execute('SELECT * FROM revision_dependencies WHERE project_id=? AND consumer_revision_id=? ORDER BY consumer_item_id,dependency_id',(project_id,revision_id)):
        value={'dependency_id':r['dependency_id'],'object_id':r['producer_object_id'],'revision_id':r['producer_revision_id'],'item_id':r['producer_item_id'],'fingerprint':r['fingerprint'],'kind':r['dependency_kind']}
        row['dependencies'].setdefault(r['consumer_item_id'],[]).append(value)
    return row

def selected_items(revision, item_id):
    entries=revision['payload'].get('items',revision['payload'].get('blocks',[]))
    key='item_id' if 'items' in revision['payload'] else 'block_id'
    if item_id=='*': return entries
    chosen=[i for i in entries if i[key]==item_id]
    if not chosen: raise YuError('INVALID_ITEM_REFERENCE','引用的条目不存在。',details=[{'revision_id':revision['id'],'item_id':item_id}])
    return chosen

def fingerprint(db, project_id, revision_id, item_id):
    r=load_revision(db,project_id,revision_id)
    entries=selected_items(r,item_id)
    values=[]
    for entry in entries:
        key=entry.get('item_id',entry.get('block_id'))
        deps=[{k:v for k,v in d.items() if k!='revision_id'} for d in r['dependencies'].get(key,[])]
        values.append({'entry':entry,'sources':r['sources'].get(key,[]),'dependencies':deps})
    value={'items':values}
    if item_id=='*':
        value['title']=r['payload'].get('title','')
        value['order']=r['payload'].get('item_order',r['payload'].get('block_order',[]))
    return digest(value)

def is_fresh(db, project_id, revision_id, item_id, seen=None):
    seen=set() if seen is None else set(seen)
    marker=(revision_id,item_id)
    if marker in seen: return False
    seen.add(marker)
    try:
        r=load_revision(db,project_id,revision_id); o=get_object(db,project_id,r['object_id'])
        if o['archived_at'] or not o['current_revision_id']: return False
        current=load_revision(db,project_id,o['current_revision_id'])
        if fingerprint(db,project_id,revision_id,item_id)!=fingerprint(db,project_id,current['id'],item_id): return False
        for entry in selected_items(current,item_id):
            key=entry.get('item_id',entry.get('block_id'))
            for d in current['dependencies'].get(key,[]):
                if not is_fresh(db,project_id,d['revision_id'],d['item_id'],seen): return False
        return True
    except YuError as exc:
        if exc.code in {'INVALID_ITEM_REFERENCE','OBJECT_NOT_FOUND','REVISION_NOT_FOUND'}: return False
        raise

def resolve_dependency(ctx, dep):
    o=get_object(ctx.db,ctx.project_id,dep['object_id'])
    r=load_revision(ctx.db,ctx.project_id,dep['revision_id'])
    if o['layer']!='draft' or r['object_id']!=o['id']:
        raise YuError('INVALID_ITEM_REFERENCE','依据必须是所指 draft 的版本。')
    value=fingerprint(ctx.db,ctx.project_id,r['id'],dep['item_id'])
    if not is_fresh(ctx.db,ctx.project_id,r['id'],dep['item_id']):
        raise YuError('STALE_DEPENDENCY','draft 依据已变化，先更新上游。',details=[{'object_id':o['id'],'item_id':dep['item_id']}])
    return {**dep,'fingerprint':value}

def revision_content(payload, sources, dependencies):
    return {'payload':payload,'sources':{k:sorted(v,key=lambda x:x['evidence_id']) for k,v in sources.items() if v},
            'dependencies':{k:sorted(v,key=lambda x:x['dependency_id']) for k,v in dependencies.items() if v}}

def write_revision(ctx, object_id, payload, *, sources=None, dependencies=None, lineage=None, changed_items=None):
    sources,dependencies=sources or {},dependencies or {}
    o=get_object(ctx.db,ctx.project_id,object_id)
    old=o['current_revision_id']; rid=new_id('rev')
    lineage=copy.deepcopy(lineage or {})
    def finalize_lineage(value):
        if isinstance(value,dict):
            if 'last_authored_revision_id' in value and value['last_authored_revision_id'] is None:
                value['last_authored_revision_id']=rid
            for child in value.values():finalize_lineage(child)
        elif isinstance(value,list):
            for child in value:finalize_lineage(child)
    finalize_lineage(lineage)
    version=ctx.db.execute('SELECT COALESCE(MAX(version),0)+1 FROM object_revisions WHERE project_id=? AND object_id=?',(ctx.project_id,object_id)).fetchone()[0]
    insert(ctx.db,'object_revisions',project_id=ctx.project_id,id=rid,object_id=object_id,version=version,schema_version=1,
           payload_json=canonical(payload),content_hash=digest(revision_content(payload,sources,dependencies)),block_lineage_json=canonical(lineage or {}),change_id=ctx.change_id,created_at=now())
    for item_id,refs in sources.items():
        for s in refs:
            insert(ctx.db,'revision_sources',project_id=ctx.project_id,revision_id=rid,item_id=item_id,evidence_id=s['evidence_id'],
                   source_version_id=s['source_version_id'],asset_id=s.get('asset_id'),locator_json=canonical(s.get('locator',{})),evidence_kind=s['kind'])
    for item_id,refs in dependencies.items():
        for d in refs:
            insert(ctx.db,'revision_dependencies',project_id=ctx.project_id,consumer_revision_id=rid,consumer_item_id=item_id,dependency_id=d['dependency_id'],
                   producer_object_id=d['object_id'],producer_revision_id=d['revision_id'],producer_item_id=d['item_id'],fingerprint=d['fingerprint'],dependency_kind=d['kind'])
    ctx.db.execute('UPDATE object_revisions SET sealed=1 WHERE project_id=? AND id=?',(ctx.project_id,rid))
    ctx.db.execute('UPDATE objects SET current_revision_id=? WHERE project_id=? AND id=?',(rid,ctx.project_id,object_id))
    ctx.changed_refs.append({'object_id':object_id,'before_revision_id':old,'revision_id':rid,'item_ids':changed_items or ['*']})
    return {'object_id':object_id,'revision_id':rid,'version':version}

def affected_objects(db, project_id):
    results={'draft':[],'review':[]}
    for o in db.execute('SELECT * FROM objects WHERE project_id=? AND archived_at IS NULL AND current_revision_id IS NOT NULL',(project_id,)).fetchall():
        r=load_revision(db,project_id,o['current_revision_id'])
        stale=[]
        for item_id,deps in r['dependencies'].items():
            if any(not is_fresh(db,project_id,d['revision_id'],d['item_id']) for d in deps): stale.append(item_id)
        if stale: results[o['layer']].append({'object_id':o['id'],'block_ids' if o['layer']=='review' else 'item_ids':stale,'reason':'dependency_changed'})
    return results
