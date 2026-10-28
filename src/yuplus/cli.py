"""Machine-friendly CLI; domain writes are accessible only through command handlers."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from .app import App, LIFECYCLE_COMMANDS
from .core import YuError

COMMANDS={
    'project.create','project.rename','project.delete','project.list','project.show','source.import','source.list','source.show',
    'draft.apply','draft.list','draft.show','review.prepare','review.publish','review.list','review.show',
    'changes.list','decisions.list','types.show','doctor','serve','start','stop','status',
    'export.record','export.list','backup.create','backup.verify','backup.restore','source.check',
}
from .case_research import ACTIONS as RESEARCH_ACTIONS
COMMANDS.update("research."+action for action in RESEARCH_ACTIONS)
from .case_library import ACTIONS as LIBRARY_ACTIONS
COMMANDS.update({'logo.show','logo.set','logo.reset'})
COMMANDS.update('library.'+action for action in LIBRARY_ACTIONS)
COMMANDS.update(LIFECYCLE_COMMANDS)
INPUT_COMMANDS={'research.create','research.update','logo.set','logo.reset','export.record','source.import','draft.apply','review.prepare','review.publish'} | LIFECYCLE_COMMANDS | {'library.'+a for a in LIBRARY_ACTIONS-{'list','show'}}
MONITOR_ACTIONS={'add','list','show','runs','schedule','scheduler-bind','update','pause','resume','remove',
                 'begin','fetch','pending','steps','read','renew','capture','step','discard-step','resolve','finish'}
COMMANDS.update('monitor.'+action for action in MONITOR_ACTIONS)

class Parser(argparse.ArgumentParser):
    def error(self,message): raise YuError('INVALID_INPUT',message)

def reject_duplicate(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise YuError('INVALID_INPUT','JSON 含有重复字段。',details=[{'field':key}])
        result[key]=value
    return result

def parse_json(text):
    def bad_constant(value):raise YuError('INVALID_INPUT','JSON 不允许 NaN 或 Infinity。')
    try:
        value=json.loads(text,object_pairs_hook=reject_duplicate,parse_constant=bad_constant)
        def check(v):
            if type(v) is int and abs(v)>9007199254740991:raise YuError('INVALID_INPUT','大整数请使用字符串。')
            if isinstance(v,dict):
                for x in v.values():check(x)
            elif isinstance(v,list):
                for x in v:check(x)
        check(value)
        return value
    except (json.JSONDecodeError,UnicodeError,RecursionError) as exc:raise YuError('INVALID_INPUT','无法解析 JSON 输入。') from exc

def default_data_dir():
    if os.environ.get('YUPLUS_DATA_DIR'):return os.environ['YUPLUS_DATA_DIR']
    receipt=Path(sys.prefix).parent/'installation.json'
    if receipt.is_file():
        try:
            value=json.loads(receipt.read_text())
            if isinstance(value,dict) and Path(value.get('cli','')).resolve()==(Path(sys.prefix)/'bin/yu').resolve() and isinstance(value.get('data_dir'),str) and Path(value['data_dir']).is_absolute():return value['data_dir']
        except (OSError,ValueError,TypeError):pass
        raise YuError('INVALID_INPUT','安装记录损坏或与当前 CLI 不匹配；请明确指定 --data-dir 或重新运行安装入口。')
    return str(Path.home()/'.local/share/yuplus')


def main(argv=None):
    parser=Parser(prog='yu',description='Yu+ 本地项目与来源 CLI（v0.3.22）',
                  epilog='案例库 library：只保存类型、名称和链接；kind 为 feishu_folder 或 website，分别由 Agent 按需使用飞书 CLI 或浏览器查找，不缓存内容。\nlibrary delete/restore 仅移除/恢复本地登记，不删除飞书文件夹或网站内容。\n可用命令：\n'+'\n'.join('  '+c.replace('.',' ') for c in sorted(COMMANDS)),
                  formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('resource',nargs='?');parser.add_argument('action',nargs='?')
    parser.add_argument('--data-dir')
    parser.add_argument('--port',type=int,default=7801,help='serve 本地端口（0 自动分配）')
    parser.add_argument('--include-deleted',action='store_true',help='project/source/draft/review/library list: 包含软删除记录')
    parser.add_argument('--base-version',type=int,help='project rename/delete: project show 返回的 metadata_version')
    parser.add_argument('--project');parser.add_argument('--request-id');parser.add_argument('--input')
    parser.add_argument('--research',help='找案例研究 ID（research show/preview）')
    parser.add_argument('--monitor');parser.add_argument('--library',help='案例库 ID（library show）')
    parser.add_argument('--output');parser.add_argument('--name');parser.add_argument('--source');parser.add_argument('--snapshot')
    parser.add_argument('--include-body',action='store_true',help='source show 显式读取来源正文')
    parser.add_argument('--object');parser.add_argument('--revision');parser.add_argument('--type',dest='type_key')
    parser.add_argument('--limit',type=int,default=50);parser.add_argument('--after-cursor',default=0)
    parser.add_argument('--json',action='store_true',help='输出稳定 JSON（默认同样输出 JSON）')
    app=None;args=None;command='unknown'
    try:
        args=parser.parse_args(argv)
        args.data_dir=args.data_dir or default_data_dir()
        command='.'.join(x for x in (args.resource,args.action) if x)
        if command not in COMMANDS:raise YuError('INVALID_INPUT','未知命令，请运行 yu --help。')
        if command in INPUT_COMMANDS or (args.resource=='monitor' and (args.input or args.action not in {'list','show','runs','schedule'})):
            if not args.input:raise YuError('INVALID_INPUT','该命令需要 --input 文件或 --input -。')
            if args.input=='-':raw=sys.stdin.buffer.read(8*1024*1024+1)
            else:
                with open(args.input,'rb') as file:raw=file.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise YuError('INPUT_TOO_LARGE','单次 JSON 不能超过 8 MiB。')
            try:payload=parse_json(raw.decode('utf-8'))
            except UnicodeDecodeError as exc:raise YuError('INVALID_INPUT','输入必须是 UTF-8。') from exc
        elif command=='project.delete':
            if args.input:raise YuError('INVALID_INPUT','删除项目使用 --project 与 --base-version，不接受 --input。')
            payload={'base_metadata_version':args.base_version}
        elif command in {'project.create','project.rename'}:
            if not args.name:raise YuError('INVALID_INPUT','创建或重命名项目需要 --name。')
            if args.input:raise YuError('INVALID_INPUT','项目名称通过 --name 提供，不接受 --input。')
            payload={'name':args.name}
            if command=='project.rename':payload['base_metadata_version']=args.base_version
        else:
            payload={}
            if command in {'project.list','source.list','draft.list','review.list','library.list'}:payload['include_deleted']=args.include_deleted
            mapping={'source_id':args.source,'snapshot_id':args.snapshot,'object_id':args.object,'revision_id':args.revision,'type_key':args.type_key}
            if args.research:payload['research_id']=args.research
            if args.library:payload['library_id']=args.library
            if args.monitor:payload['monitor_id']=args.monitor
            payload.update({k:v for k,v in mapping.items() if v is not None})
            if args.include_body:payload['include_body']=True
            if command.endswith('.show') and command.startswith(('draft.','review.')) and not args.object:raise YuError('INVALID_INPUT','需要 --object。')
            if command=='source.show' and not args.source:raise YuError('INVALID_INPUT','需要 --source。')
            if command in {'changes.list','decisions.list'}:payload.update(limit=args.limit,after_cursor=args.after_cursor)
        if command in {'start','stop','status','backup.create','backup.verify','backup.restore','source.check'}:
            if command in {'start','stop','status'}:
                if command=='start':
                    check=App(args.data_dir);check.close()
                from .service import control
                data=control(args.data_dir,command)
            elif command=='source.check':
                from .source_check import scan
                data=scan(args.data_dir,args.project,args.source)
            else:
                from .backup import create_backup,verify_backup,restore_backup
                if command=='backup.create':
                    if not args.output:raise YuError('INVALID_INPUT','需要 --output 新目录。')
                    data=create_backup(args.data_dir,args.output)
                else:
                    if not args.input:raise YuError('INVALID_INPUT','需要 --input 备份目录。')
                    data=verify_backup(args.input) if command=='backup.verify' else restore_backup(args.input,args.data_dir)
            print(json.dumps({'api_version':'1','command':command,'ok':True,'data':data},ensure_ascii=False));return 0
        app=App(args.data_dir)
        if command=='serve':
            app.close();app=None
            from .gateway import serve
            return serve(args.data_dir,args.port)
        if args.resource=='monitor':
            from .monitor import Monitor
            result=app._envelope(command,args.project,None,Monitor(app).execute(args.action,payload,args.project))
        else:result=app.execute(command,payload,project_id=args.project,request_id=args.request_id)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except YuError as exc:error=exc
    except FileNotFoundError as exc:error=YuError('FILE_NOT_FOUND','输入文件不存在。',details=[{'path':str(exc.filename)}])
    except OSError as exc:error=YuError('DISK_FULL' if exc.errno==28 else 'IO_FAILURE','本地文件操作失败。',details=[{'reason':str(exc)}])
    except sqlite3.OperationalError as exc:
        error=YuError('DATABASE_BUSY' if 'locked' in str(exc).lower() or 'busy' in str(exc).lower() else 'INTEGRITY_FAILURE','数据库暂时忙碌。' if 'locked' in str(exc).lower() else '数据库操作失败。',retryable='locked' in str(exc).lower())
    except sqlite3.IntegrityError as exc:error=YuError('INTEGRITY_FAILURE','数据库约束拒绝提交。',details=[{'constraint':str(exc)}])
    except sqlite3.DatabaseError as exc:error=YuError('INTEGRITY_FAILURE','数据库无法读取，已保留原文件。',details=[{'reason':str(exc)}])
    except (KeyError,TypeError,ValueError,RecursionError) as exc:error=YuError('INVALID_INPUT','输入缺少字段或格式不正确。',details=[{'reason':str(exc)[:200]}])
    finally:
        if app is not None:app.close()
    result={'api_version':'1','command':command or 'unknown','ok':False,'project_id':args.project if args else None,'request_id':args.request_id if args else None,
            'error':{'code':error.code,'message':error.message,'retryable':error.retryable,'details':error.details,'next_action':error.next_action},
            'meta':{'change_id':None,'history_cursor':None,'replayed':False}}
    print(json.dumps(result,ensure_ascii=False,allow_nan=False));return error.exit_code
