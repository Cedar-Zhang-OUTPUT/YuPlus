"""Verified export receipts, persisted in the existing append-only change history."""
import json
import re
from urllib.parse import urlsplit
from .core import YuError, get_object, load_revision, new_id, now


def validate(payload):
    required={'api_version','command','external_title','external_url','view_basis','content_sha256','verified'}
    if set(payload)!=required or payload.get('api_version')!='1' or payload.get('command')!='export.record' or payload.get('verified') is not True:
        raise YuError('INVALID_INPUT','仅在飞书正文与来源附录回读核验完成后提交 export.record，需 verified: true。')
    title=payload['external_title']
    if not isinstance(title,str) or not title.strip() or len(title)>500:
        raise YuError('INVALID_INPUT','需要真实文档标题（最多 500 字）。')
    value=payload['external_url']
    try:
        if not isinstance(value,str) or len(value)>4096 or any(ord(c)<33 for c in value) or '\\' in value:raise ValueError()
        url=urlsplit(value);host=(url.hostname or '').lower()
        if url.scheme!='https' or url.username or url.password or url.port not in (None,443) or not any(host==d or host.endswith('.'+d) for d in ('feishu.cn','larksuite.com')) or not re.fullmatch(r'/(docx|docs|wiki)/[A-Za-z0-9_-]+/?',url.path):raise ValueError()
    except ValueError:
        raise YuError('INVALID_INPUT','需要可打开的 https 飞书云文档链接。') from None
    if not isinstance(payload['content_sha256'],str) or not re.fullmatch(r'[a-f0-9]{64}',payload['content_sha256']):
        raise YuError('INVALID_INPUT','需要最终发布稿的 SHA256（64 位小写十六进制）。')
    basis=payload['view_basis']
    if not isinstance(basis,list) or not basis or len(basis)>1000:
        raise YuError('INVALID_INPUT','需要实际导出的非空成果版本清单。')
    seen=set()
    for entry in basis:
        if not isinstance(entry,dict) or set(entry)!={'object_id','revision_id'} or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}',v) for v in entry.values()):
            raise YuError('INVALID_INPUT','版本清单需要 object_id 和 revision_id。')
        if entry['object_id'] in seen:raise YuError('INVALID_INPUT','版本清单不可重复对象。')
        seen.add(entry['object_id'])


def records(db,pid):
    # The command receipt is the canonical record: no second copy or source import.
    return [json.loads(row['result_json']) for row in db.execute(
        "SELECT result_json FROM changes WHERE project_id=? AND command='export.record' ORDER BY seq DESC",(pid,))]


def record(ctx,payload):
    for entry in payload['view_basis']:
        obj=get_object(ctx.db,ctx.project_id,entry['object_id'])
        revision=load_revision(ctx.db,ctx.project_id,entry['revision_id'])
        if revision['object_id']!=obj['id'] or not (obj['layer']=='review' or obj['type_key']=='qa'):
            raise YuError('INVALID_INPUT','导出版本必须属于本项目的 Review 或共享客户 Q&A。')
    # A concurrent edit is allowed: the receipt describes the versions actually exported.
    url=urlsplit(payload['external_url'])
    clean=url._replace(query='',fragment='',path=url.path.rstrip('/')).geturl()
    if any(row['external_url']==clean for row in records(ctx.db,ctx.project_id)):
        raise YuError('ALREADY_EXISTS','该飞书文档已有导出记录；重试请复用原 request-id。')
    result={'id':new_id('exp'),'project_id':ctx.project_id,'destination':'feishu',
            'external_title':payload['external_title'].strip(),'external_url':clean,
            'view_basis':payload['view_basis'],'content_sha256':payload['content_sha256'],
            'exported_at':now(),'verification':'agent_readback','change_id':ctx.change_id}
    ctx.changed_refs.append({'export_id':result['id']})
    return result
