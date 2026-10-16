"""Bounded lark-cli adapter. Never logs credentials or invokes a shell."""
import json
import os
import re
import subprocess
from urllib.parse import urlsplit
from .core import YuError


def run_lark(args, *, cwd=None, timeout=30):
    env={**os.environ,'LARKSUITE_CLI_NO_UPDATE_NOTIFIER':'1','LARKSUITE_CLI_NO_SKILLS_NOTIFIER':'1'}
    try:
        result=subprocess.run(['lark-cli',*args],cwd=cwd,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise YuError('FEISHU_UNAVAILABLE','飞书 CLI 不可用或检查超时。') from exc
    try: response=json.loads(result.stdout if result.returncode==0 else result.stderr)
    except (ValueError,TypeError) as exc: raise YuError('FEISHU_UNAVAILABLE','飞书 CLI 返回无法识别的结果。') from exc
    if not isinstance(response,dict):raise YuError('FEISHU_UNAVAILABLE','飞书 CLI 返回无法识别的结果。')
    if result.returncode!=0 or response.get('ok') is not True:
        error=response.get('error',{})
        if not isinstance(error,dict):error={}
        raise YuError('FEISHU_UNAVAILABLE','飞书调用未成功，请按 lark-shared 检查认证与权限。',details=[{'provider_code':error.get('code'),'type':error.get('type'),'subtype':error.get('subtype')}])
    data=response.get('data',{})
    if not isinstance(data,dict):raise YuError('FEISHU_UNAVAILABLE','飞书 CLI 未返回有效数据。')
    return data


def observe(source):
    url=source.get('canonical_url')
    parts=urlsplit(url or '')
    segments=parts.path.strip('/').split('/')
    if parts.scheme!='https' or parts.username or parts.password or len(segments)<2:
        raise YuError('SOURCE_CHECK_UNSUPPORTED','来源没有可检查的飞书地址。')
    kind,token=segments[-2:]
    kind={'sheets':'sheet','base':'bitable'}.get(kind,kind)
    if kind=='wiki':
        data=run_lark(['drive','+inspect','--as','user','--url',url])
        kind,token=data.get('type'),data.get('token')
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',token): raise YuError('SOURCE_CHECK_UNSUPPORTED','无法识别飞书资源身份。')
    if kind=='docx':
        doc=run_lark(['docs','+fetch','--as','user','--doc',token,'--scope','outline','--max-depth','1']).get('document',{})
        revision=doc.get('revision_id') if isinstance(doc,dict) else None
        if type(revision) is not int or revision<0: raise YuError('SOURCE_CHECK_UNSUPPORTED','未返回可比较的文档版本。')
        return {'marker':str(revision),'kind':'revision','resource_type':kind,'token':token}
    if kind not in {'doc','sheet','bitable','mindnote','file','folder','slides'}:
        raise YuError('SOURCE_CHECK_UNSUPPORTED','该来源暂不支持版本检查。')
    result=run_lark(['drive','metas','batch_query','--as','user','--data',json.dumps({'request_docs':[{'doc_token':token,'doc_type':kind}]})])
    metas=result.get('metas')
    meta=next((m for m in metas if isinstance(m,dict) and m.get('doc_token')==token),None) if isinstance(metas,list) else None
    if not meta or not meta.get('latest_modify_time'): raise YuError('FEISHU_UNAVAILABLE','无法读取该资源的修改时间。')
    return {'marker':'mtime:'+str(meta['latest_modify_time']),'kind':'modified_time','resource_type':kind,'token':token}
