"""Durable chat intake and fenced Agent work, without a model or scheduler daemon."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import re
from .message_time import message_time
from .core import YuError, canonical, digest, new_id, now, affected_objects


def instant(value):
    try:
        return message_time(value).isoformat(timespec='microseconds').replace('+00:00','Z')
    except (ValueError,TypeError,AttributeError,OverflowError,OSError): raise YuError('INVALID_INPUT','消息时间无效。')


def shifted(value, seconds):
    return (datetime.fromisoformat(value.replace('Z','+00:00'))+timedelta(seconds=seconds)).isoformat().replace('+00:00','Z')


def summaries(db, project_id=None):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='chat_monitors'").fetchone(): return []
    sql='SELECT * FROM chat_monitors'+(' WHERE project_id=?' if project_id else '')+' ORDER BY created_at,id'
    result=[]
    for row in db.execute(sql,(project_id,) if project_id else ()):
        m=dict(row);m['monitor_id']=m['id'];m['history_complete']=bool(m['history_complete'])
        m['schedule']=json.loads(m.pop('schedule_json'));m.pop('threads_json');m.pop('identity')
        m['pending_count']=db.execute('SELECT count(*) FROM monitor_messages WHERE monitor_id=? AND disposition IS NULL',(m['id'],)).fetchone()[0]
        m['clarification_count']=db.execute("SELECT count(*) FROM monitor_messages WHERE monitor_id=? AND disposition='clarification'",(m['id'],)).fetchone()[0]
        result.append(m)
    return result


class Monitor:
    def __init__(self,app,reader=None): self.app=app;self.db=app.db;self._reader=reader
    @property
    def reader(self):
        if self._reader is None:
            from .chat_reader import FeishuChatReader
            self._reader=FeishuChatReader()
        return self._reader
    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try: yield;self.db.execute('COMMIT')
        except BaseException: self.db.execute('ROLLBACK');raise
    def monitor(self,pid,mid):
        row=self.db.execute('SELECT * FROM chat_monitors WHERE project_id=? AND id=?',(pid,mid)).fetchone()
        if not row: raise YuError('MONITOR_NOT_FOUND','项目中未找到该群聊监控。')
        return dict(row)
    def guard(self,pid,p):
        run=self.db.execute('SELECT * FROM monitor_runs WHERE project_id=? AND id=?',(pid,p.get('run_id'))).fetchone()
        if not run: raise YuError('MONITOR_NOT_FOUND','同步批次不属于此项目。')
        m=self.monitor(pid,run['monitor_id'])
        lease=self.db.execute('SELECT * FROM monitor_leases WHERE project_id=?',(pid,)).fetchone()
        if m['status']!='enabled' or not lease or lease['run_id']!=run['id'] or lease['token']!=p.get('token') or lease['expires_at']<=now():
            raise YuError('MONITOR_LEASE_LOST','监控已暂停或执行租约失效；重新 begin 后继续。')
        if run['status']=='complete': raise YuError('MONITOR_RUN_COMPLETE','该同步批次已结束。')
        return dict(run),m
    def execute(self,action,p,pid):
        if not isinstance(p,dict): raise YuError('INVALID_INPUT','monitor 输入必须为 JSON 对象。')
        auth={'run_id','token'}
        fields={'add':{'chat_id','interval_minutes'},'list':set(),'show':{'monitor_id'},'runs':{'monitor_id'},'schedule':{'monitor_id'},
                'scheduler-bind':{'monitor_id','version','schedule'},'update':{'monitor_id','version','interval_minutes'},
                **{a:{'monitor_id','version'} for a in ('pause','resume','remove')},'begin':{'monitor_id','force'},
                'fetch':auth|{'page_budget','restart_window'},'pending':auth|{'limit'},'steps':auth|{'limit','after_step'},
                'read':auth|{'message_version'},'renew':auth,'capture':auth|{'message_version','message_versions','title'},
                'step':auth|{'step_key','command','input','message_versions'},'discard-step':auth|{'step_key','reason'},
                'resolve':auth|{'message_versions','outcome','reason','change_ids'},'finish':auth|{'summary'}}
        if action not in fields or set(p)-fields[action]:raise YuError('INVALID_INPUT','未知 monitor 命令或输入字段。')
        for flag in ('force','restart_window'):
            if flag in p and type(p[flag]) is not bool:raise YuError('INVALID_INPUT',flag+' 必须为布尔值。')
        if 'version' in p and type(p['version']) is not int:raise YuError('INVALID_INPUT','version 必须为整数。')
        self.app._project(pid,action not in {'list','show','runs','read','pending','steps','schedule'})
        actions={'add':self.add,'begin':self.begin,'fetch':self.fetch,'pending':self.pending,'step':self.step,
                 'capture':self.capture,'resolve':self.resolve,'finish':self.finish,'discard-step':self.discard_step}
        if action in actions: return actions[action](pid,p)
        if action=='list':return {'monitors':summaries(self.db,pid)}
        if action=='show':
            self.monitor(pid,p.get('monitor_id'))
            return next(m for m in summaries(self.db,pid) if m['id']==p['monitor_id'])
        if action=='runs':
            self.monitor(pid,p.get('monitor_id'))
            return {'runs':[dict(r) for r in self.db.execute('SELECT id,monitor_id,project_id,status,created_at AS started_at,completed_at,summary,fetch_complete FROM monitor_runs WHERE project_id=? AND monitor_id=? ORDER BY created_at DESC LIMIT 30',(pid,p['monitor_id']))]}
        if action=='steps':
            run,_=self.guard(pid,p);limit=p.get('limit',25);after=p.get('after_step')
            if type(limit) is not int or not 1<=limit<=100:raise YuError('INVALID_INPUT','limit 范围 1–100。')
            stamp='';key=''
            if after:
                row=self.db.execute('SELECT created_at,step_key FROM monitor_steps WHERE run_id=? AND step_key=?',(run['id'],after)).fetchone()
                if not row:raise YuError('INVALID_INPUT','after_step 不属于当前批次。')
                stamp,key=row
            rows=list(self.db.execute('SELECT * FROM monitor_steps WHERE run_id=? AND (created_at>? OR (created_at=? AND step_key>?)) ORDER BY created_at,step_key LIMIT ?',(run['id'],stamp,stamp,key,limit+1)))
            return {'steps':[{'step_key':r['step_key'],'command':r['command'],'message_versions':json.loads(r['message_versions_json']),
                             'result':json.loads(r['result_json']) if r['result_json'] else None} for r in rows[:limit]],
                    'next_after_step':rows[limit-1]['step_key'] if len(rows)>limit else None}
        if action=='renew':
            with self.transaction():
                self.guard(pid,p);self.db.execute('UPDATE monitor_leases SET expires_at=? WHERE project_id=?',(shifted(now(),600),pid))
            return {'renewed':True}
        if action=='read':
            run,m=self.guard(pid,p)
            row=self.db.execute('SELECT * FROM monitor_messages WHERE monitor_id=? AND id=?',(m['id'],p.get('message_version'))).fetchone()
            if not row:raise YuError('MONITOR_NOT_FOUND','消息版本不属于该监控。')
            return self.message(row)
        if action in {'update','pause','resume','remove','scheduler-bind','schedule'}:return self.configure(pid,action,p)
        raise YuError('INVALID_INPUT','未知 monitor 命令。')
    def add(self,pid,p):
        if not re.fullmatch(r'oc_[A-Za-z0-9_-]+',str(p.get('chat_id',''))):raise YuError('INVALID_INPUT','需要核实后的 oc_ 群 ID。')
        interval=p.get('interval_minutes',60)
        if type(interval) is not int or not 1<=interval<=525600:raise YuError('INVALID_INPUT','interval_minutes 必须为正整数分钟（最多一年）。')
        info=self.reader.info(p['chat_id'])
        with self.transaction():
            old=self.db.execute('SELECT id FROM chat_monitors WHERE project_id=? AND identity=? AND chat_id=?',(pid,info['identity'],p['chat_id'])).fetchone()
            if old:return {'monitor_id':old['id'],'reused':True}
            mid=new_id('mon');stamp=now()
            self.db.execute('INSERT INTO chat_monitors(id,project_id,chat_id,identity,chat_name,chat_url,status,interval_minutes,next_due_at,created_at) VALUES(?,?,?,?,?,?,\'enabled\',?,?,?)',(mid,pid,p['chat_id'],info['identity'],info['name'],info['url'],interval,stamp,stamp))
        return {'monitor_id':mid,'reused':False,'history_scope':'all_accessible','scheduler_state':'pending'}
    def configure(self,pid,action,p):
        m=self.monitor(pid,p.get('monitor_id'))
        if action=='schedule':
            return {'monitor_id':m['id'],'interval_minutes':m['interval_minutes'],'schedule':json.loads(m['schedule_json']),
                    'prompt':f'Use the installed yuplus Skill chat-monitoring reference. Maintain ONLY project {pid}, monitor {m["id"]}, data directory {self.app.data_dir}. Call monitor begin; resume durable progress, fetch all accessible history initially, then process chronological batches. Update draft and affected existing review through monitor step. Preserve evidence and decisions. Finish only verified work; report meaningful changes or blockers, stay quiet for empty checks. Check binding still enabled every run.',
                    'requires_host_automation_tool':True}
        with self.transaction():
            m=self.monitor(pid,m['id'])
            if p.get('version')!=m['version']:raise YuError('BASE_REVISION_CONFLICT','监控配置已变化，请重新读取 version。')
            if action=='scheduler-bind':
                receipt=p.get('schedule',{})
                if not isinstance(receipt,dict) or receipt.get('state') not in ('active','paused','error') or any(not isinstance(receipt.get(k),str) or not receipt[k].strip() for k in ('automation_id','thread_id','host_id')):
                    raise YuError('INVALID_INPUT','需要实际宿主 automation_id、thread_id、host_id 和 state。')
                if receipt.get('interval_minutes')!=m['interval_minutes']:raise YuError('INVALID_INPUT','实际调度间隔与配置不一致。')
                receipt={k:receipt[k] for k in ('automation_id','thread_id','host_id','state','interval_minutes')};receipt['verified_at']=now()
                self.db.execute('UPDATE chat_monitors SET schedule_json=?,version=version+1 WHERE id=?',(canonical(receipt),m['id']))
            elif action=='update':
                interval=p.get('interval_minutes')
                if type(interval) is not int or not 1<=interval<=525600:raise YuError('INVALID_INPUT','需要有效 interval_minutes。')
                schedule=json.loads(m['schedule_json']);schedule['state']='pending'
                self.db.execute('UPDATE chat_monitors SET interval_minutes=?,schedule_json=?,version=version+1,next_due_at=? WHERE id=?',(interval,canonical(schedule),now(),m['id']))
            else:
                state={'pause':'paused','resume':'enabled','remove':'removed'}[action]
                schedule=json.loads(m['schedule_json']);schedule['state']='pending'
                self.db.execute('UPDATE chat_monitors SET status=?,version=version+1,schedule_json=?,next_due_at=? WHERE id=?',(state,canonical(schedule),now(),m['id']))
                self.db.execute('DELETE FROM monitor_leases WHERE project_id=? AND run_id IN (SELECT id FROM monitor_runs WHERE monitor_id=?)',(pid,m['id']))
        return self.execute('show',{'monitor_id':m['id']},pid)
    def begin(self,pid,p):
        with self.transaction():
            m=self.monitor(pid,p.get('monitor_id'));stamp=now()
            if m['status']!='enabled':raise YuError('MONITOR_PAUSED','监控未启用。')
            lease=self.db.execute('SELECT * FROM monitor_leases WHERE project_id=?',(pid,)).fetchone()
            if lease and lease['expires_at']>stamp:raise YuError('MONITOR_BUSY','该项目有正在执行的自动同步；不能抢占有效租约。',retryable=True)
            run=self.db.execute("SELECT * FROM monitor_runs WHERE monitor_id=? AND status!='complete' ORDER BY created_at LIMIT 1",(m['id'],)).fetchone()
            if not run:
                if m['fetched_through'] and stamp<m['fetched_through']:
                    raise YuError('MONITOR_CLOCK_SKEW','本机时间早于已保存的读取截止时间；请校准时间后重试，进度未改变。')
                if not p.get('force') and m['next_due_at']>stamp:return {'due':False,'next_due_at':m['next_due_at']}
                rid=new_id('run');start=shifted(m['fetched_through'],-300) if m['fetched_through'] else None
                recheck=not m['last_recheck_at'] or shifted(m['last_recheck_at'],86400)<=stamp
                ids=[r[0] for r in self.db.execute('''SELECT DISTINCT mm.message_id FROM monitor_messages mm
                    WHERE mm.monitor_id=? AND (mm.created_at>=? OR (? AND EXISTS(
                      SELECT 1 FROM sources s JOIN source_versions sv ON sv.project_id=s.project_id AND sv.source_id=s.id
                      JOIN revision_sources rs ON rs.project_id=sv.project_id AND rs.source_version_id=sv.id
                      JOIN objects o ON o.project_id=rs.project_id AND o.current_revision_id=rs.revision_id
                      WHERE s.project_id=? AND s.provider='feishu' AND ((s.resource_type='message' AND s.provider_key=? || ':' || mm.message_id)
                         OR (s.resource_type='chat_segment' AND EXISTS (
                           SELECT 1 FROM monitor_steps st, json_each(st.message_versions_json) member
                           JOIN monitor_messages evidence ON evidence.id=member.value
                           WHERE evidence.monitor_id=mm.monitor_id AND evidence.message_id=mm.message_id
                             AND st.command='source.import' AND st.result_json IS NOT NULL
                             AND json_extract(st.result_json,'$.data.snapshot_id')=sv.id)))))) ORDER BY mm.message_id''',
                    (m['id'],shifted(stamp,-86400),int(recheck),pid,m['identity']+':'+m['chat_id']))]
                cursor={'phase':'roots','page_token':None,'threads':json.loads(m['threads_json']),'thread_index':0,'recheck_ids':ids,'detail_index':0,'daily_recheck':recheck}
                self.db.execute("INSERT INTO monitor_runs(id,monitor_id,project_id,status,window_start,window_end,cursor_json,initial,created_at) VALUES(?,?,?,'fetching',?,?,?,?,?)",(rid,m['id'],pid,start,stamp,canonical(cursor),int(not m['history_complete']),stamp))
            else:rid=run['id']
            token=new_id('lease')
            self.db.execute('INSERT INTO monitor_leases(project_id,run_id,token,expires_at) VALUES(?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET run_id=excluded.run_id,token=excluded.token,expires_at=excluded.expires_at',(pid,rid,token,shifted(stamp,600)))
        return {'due':True,'run_id':rid,'token':token,'resumed':bool(run),'lease_seconds':600}
    def _store(self,m,msg,cutoff,cursor):
        if not isinstance(msg,dict) or not re.fullmatch(r'om_[A-Za-z0-9_-]+',str(msg.get('message_id',''))):raise YuError('FEISHU_UNAVAILABLE','群消息缺少稳定身份。')
        created=instant(msg.get('create_time'))
        if created>cutoff:return
        thread=msg.get('thread_id')
        if thread and thread not in cursor['threads']:cursor['threads'].append(thread)
        if msg.get('thread_replies_error') and not thread:raise YuError('FEISHU_UNAVAILABLE','话题展开失败且没有可续读身份。')
        clean={k:msg[k] for k in ('message_id','msg_type','create_time','content','sender','deleted','updated','update_time','thread_id','message_app_link','mentions','root_id','parent_id') if k in msg}
        fingerprint=digest({k:v for k,v in clean.items() if k not in ('updated','update_time','message_app_link','sender','thread_id','root_id','parent_id')})
        old=self.db.execute('SELECT * FROM monitor_messages WHERE monitor_id=? AND message_id=? ORDER BY version DESC LIMIT 1',(m['id'],msg['message_id'])).fetchone()
        remote=instant(msg['update_time']) if msg.get('update_time') else None
        if old and old['remote_updated_at'] and remote and remote<old['remote_updated_at']:return
        if not old or fingerprint!=old['fingerprint']:
            self.db.execute('INSERT INTO monitor_messages(id,monitor_id,message_id,version,fingerprint,created_at,observed_at,remote_updated_at,payload_json) VALUES(?,?,?,?,?,?,?,?,?)',(new_id('mv'),m['id'],msg['message_id'],old['version']+1 if old else 1,fingerprint,created,now(),remote,canonical(clean)))
        else:
            # Preserve richer thread context and newer edit watermarks without
            # manufacturing a content edit when two read endpoints differ in metadata.
            previous=json.loads(old['payload_json'])
            for key in ('thread_id','root_id','parent_id'):
                if not previous.get(key) and clean.get(key):previous[key]=clean[key]
            watermark=max(filter(None,(remote,old['remote_updated_at'])),default=None)
            self.db.execute('UPDATE monitor_messages SET remote_updated_at=?,payload_json=? WHERE id=?',(watermark,canonical(previous),old['id']))
        for reply in msg.get('thread_replies',[]):
            contextual={**reply}
            if thread:contextual.setdefault('thread_id',thread)
            # Auto-expanded replies can be attached to any member of a thread;
            # the enclosing message is not necessarily their root or parent.
            self._store(m,contextual,cutoff,cursor)
    def fetch(self,pid,p):
        budget=p.get('page_budget',20)
        if type(budget) is not int or not 1<=budget<=100:raise YuError('INVALID_INPUT','page_budget 范围为 1–100。')
        run,m=self.guard(pid,p)
        if run['fetch_complete']:return {'fetch_complete':True,'run_id':run['id']}
        if p.get('restart_window'):
            with self.transaction():
                run,m=self.guard(pid,p);cursor=json.loads(run['cursor_json'])
                cursor.update(phase='roots',page_token=None,thread_index=0,detail_index=0)
                self.db.execute('UPDATE monitor_runs SET cursor_json=? WHERE id=?',(canonical(cursor),run['id']))
        try:
            info=self.reader.info(m['chat_id'])
            if info['identity']!=m['identity']:raise YuError('FEISHU_IDENTITY_CHANGED','飞书身份变化，未继续读取或写入。')
            for _ in range(budget):
                run,m=self.guard(pid,p);cursor=json.loads(run['cursor_json']);phase=cursor['phase']
                if phase=='done':break
                token=cursor['page_token'];messages=[]
                if phase=='roots':
                    page=self.reader.messages(m['chat_id'],run['window_start'],run['window_end'],token)
                elif phase=='threads':
                    if cursor['thread_index']>=len(cursor['threads']):
                        cursor['phase']='details';page=None
                    else:page=self.reader.replies(cursor['threads'][cursor['thread_index']],token)
                else:
                    ids=cursor['recheck_ids'][cursor['detail_index']:cursor['detail_index']+50]
                    if not ids:cursor['phase']='done';page=None
                    else:
                        messages=self.reader.details(ids);cursor['detail_index']+=len(ids);page=None
                if page is not None:
                    messages=page['messages']
                    if phase=='threads':
                        messages=[{'thread_id':cursor['threads'][cursor['thread_index']],**msg} for msg in messages]
                    if page['has_more']:
                        nxt=page.get('page_token')
                        if not nxt or nxt==token:raise YuError('FEISHU_UNAVAILABLE','分页未前进，保留当前窗口。')
                        cursor['page_token']=nxt
                    else:
                        cursor['page_token']=None
                        if phase=='roots':cursor['phase']='threads'
                        else:cursor['thread_index']+=1
                with self.transaction():
                    current,_=self.guard(pid,p)
                    if current['cursor_json']!=run['cursor_json']:raise YuError('MONITOR_BUSY','分页已被其他调用推进。')
                    old_count=len(cursor['threads'])
                    for msg in messages:self._store(m,msg,run['window_end'],cursor)
                    # A daily root recheck can discover replies on previously plain messages.
                    if phase=='details' and len(cursor['threads'])>old_count:
                        cursor['phase']='threads';cursor['thread_index']=old_count;cursor['page_token']=None
                    finished=cursor['phase']=='done'
                    self.db.execute('UPDATE monitor_runs SET cursor_json=?,fetch_complete=?,status=? WHERE id=?',(canonical(cursor),int(finished),'processing' if finished else 'fetching',run['id']))
                    self.db.execute('UPDATE monitor_leases SET expires_at=? WHERE project_id=?',(shifted(now(),600),pid))
                    if finished:
                        self.db.execute('UPDATE chat_monitors SET history_complete=1,fetched_through=?,last_checked_at=?,last_error=NULL,threads_json=?,chat_name=?,chat_url=?,last_recheck_at=CASE WHEN ? THEN ? ELSE last_recheck_at END WHERE id=?',(run['window_end'],now(),canonical(cursor['threads']),info['name'],info['url'],int(cursor['daily_recheck']),now(),m['id']))
                if finished:break
        except YuError as error:
            with self.transaction():
                self.guard(pid,p)
                self.db.execute('UPDATE chat_monitors SET last_checked_at=?,last_error=? WHERE id=?',(now(),error.message,m['id']))
            raise
        run,m=self.guard(pid,p)
        return {'run_id':run['id'],'fetch_complete':bool(run['fetch_complete']),'phase':json.loads(run['cursor_json'])['phase'],'pending_count':self.db.execute('SELECT count(*) FROM monitor_messages WHERE monitor_id=? AND disposition IS NULL',(m['id'],)).fetchone()[0]}
    def message(self,row):
        value=dict(row);value['message']=json.loads(value.pop('payload_json'));return value
    def pending(self,pid,p):
        run,m=self.guard(pid,p)
        if not run['fetch_complete']:raise YuError('MONITOR_FETCH_INCOMPLETE','先完成历史和话题分页，再按全局时间顺序处理。')
        limit=p.get('limit',25)
        if type(limit) is not int or not 1<=limit<=100:raise YuError('INVALID_INPUT','limit 范围 1–100。')
        rows=self.db.execute('SELECT * FROM monitor_messages WHERE monitor_id=? AND disposition IS NULL ORDER BY created_at,message_id,version LIMIT ?',(m['id'],limit)).fetchall()
        return {'run_id':run['id'],'messages':[self.message(r) for r in rows],'unfinished_steps':[{'step_key':r['step_key'],'command':r['command'],'request':json.loads(r['request_json']),'message_versions':json.loads(r['message_versions_json'])} for r in self.db.execute('SELECT * FROM monitor_steps WHERE run_id=? AND result_json IS NULL',(run['id'],))]}
    def selected(self,pid,p,allow_resolved=False):
        run,m=self.guard(pid,p)
        if not run['fetch_complete']:raise YuError('MONITOR_FETCH_INCOMPLETE','全量分页尚未完成。')
        ids=p.get('message_versions')
        if not isinstance(ids,list) or not ids or len(ids)>100 or any(not isinstance(v,str) for v in ids) or len(ids)!=len(set(ids)):
            raise YuError('INVALID_INPUT','需要 1–100 个不同消息版本 ID。')
        eligible=self.pending(pid,{**p,'limit':100})['messages'];byid={r['id']:r for r in eligible}
        if allow_resolved:
            for vid in ids:
                row=self.db.execute('SELECT * FROM monitor_messages WHERE id=? AND monitor_id=? AND resolved_run_id=?',(vid,m['id'],run['id'])).fetchone()
                if row:byid[vid]=self.message(row)
        if not set(ids)<=byid.keys():raise YuError('INVALID_INPUT','只能处理此监控最早一批尚未完成的消息版本。')
        return run,m,[byid[v] for v in ids]
    def step_guard(self,pid,p):
        run,m,rows=self.selected(pid,p,allow_resolved=p.get('command')=='review.publish')
        if p.get('command')=='draft.apply':
            first=self.pending(pid,{**p,'limit':len(rows)})['messages']
            if {r['id'] for r in first}!={r['id'] for r in rows}:raise YuError('INVALID_INPUT','draft 必须依据最早的待处理消息依次推进。')
        return run,m,rows
    def step(self,pid,p):
        command=p.get('command');key=p.get('step_key');payload=p.get('input')
        if command not in ('source.import','draft.apply','review.publish') or not isinstance(key,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,80}',key) or not isinstance(payload,dict):
            raise YuError('INVALID_INPUT','需要稳定 step_key、业务 command 和 input。')
        with self.transaction():
            run,m=self.guard(pid,p)
            previous=self.db.execute('SELECT * FROM monitor_steps WHERE run_id=? AND step_key=?',(run['id'],key)).fetchone()
            encoded=canonical(payload);versions=canonical(p.get('message_versions'))
            if previous:
                if previous['command']!=command or previous['request_json']!=encoded or previous['message_versions_json']!=versions:raise YuError('IDEMPOTENCY_CONFLICT','步骤身份已用于不同请求。')
                if previous['result_json']:return json.loads(previous['result_json'])
                request_id=previous['request_id']
            else:
                self.step_guard(pid,p);request_id='mon_'+digest([run['id'],key])[:48]
                self.db.execute('INSERT INTO monitor_steps VALUES(?,?,?,?,?,?,NULL,?)',(run['id'],key,command,encoded,request_id,versions,now()))
        def record(result):self.db.execute('UPDATE monitor_steps SET result_json=? WHERE run_id=? AND step_key=?',(canonical(result),run['id'],key))
        return self.app.execute(command,payload,project_id=pid,request_id=request_id,_guard=lambda:self.step_guard(pid,p),_record=record)
    def discard_step(self,pid,p):
        reason=p.get('reason')
        if not isinstance(reason,str) or not reason.strip():raise YuError('INVALID_INPUT','放弃未提交步骤需要说明原因。')
        with self.transaction():
            run,_=self.guard(pid,p)
            step=self.db.execute('SELECT * FROM monitor_steps WHERE run_id=? AND step_key=?',(run['id'],p.get('step_key'))).fetchone()
            if not step:raise YuError('MONITOR_NOT_FOUND','步骤不存在。')
            if step['result_json'] or self.db.execute('SELECT 1 FROM changes WHERE project_id=? AND request_id=?',(pid,step['request_id'])).fetchone():
                raise YuError('INVALID_INPUT','已提交或已结束的步骤不能放弃。')
            result={'ok':False,'abandoned':True,'reason':reason}
            self.db.execute('UPDATE monitor_steps SET result_json=? WHERE run_id=? AND step_key=?',(canonical(result),run['id'],step['step_key']))
        return result
    def capture(self,pid,p):
        if 'message_versions' in p:return self.capture_segment(pid,p)
        vid=p.get('message_version');selected={**p,'message_versions':[vid]};run,m,rows=self.selected(pid,selected);r=rows[0];msg=r['message']
        if r['source_version_id']:return {'source_version_id':r['source_version_id'],'reused':True}
        key=f'{m["identity"]}:{m["chat_id"]}:{r["message_id"]}'
        old=self.db.execute("SELECT id,latest_snapshot_id FROM sources WHERE project_id=? AND provider='feishu' AND resource_type='message' AND provider_key=?",(pid,key)).fetchone()
        target={'mode':'append','source_id':old['id'],'base_snapshot_id':old['latest_snapshot_id']} if old else {'mode':'create','provider':'feishu','resource_type':'message','provider_key':key,'canonical_url':m['chat_url']}
        if not old and isinstance(msg.get('message_app_link'),str):
            from .source import _remote_identity
            candidate={**target,'canonical_url':msg['message_app_link']}
            try:_remote_identity(candidate)
            except YuError:pass  # Keep the verified chat fallback; never fabricate a message link.
            else:target=candidate
        text=msg.get('content','');text=text if isinstance(text,str) else canonical(text)
        if msg.get('deleted'):text='[消息已撤回]\n'+text
        sender=msg.get('sender',{});name=sender.get('name',sender.get('id','未知发言者')) if isinstance(sender,dict) else str(sender)
        payload={'api_version':'1','command':'source.import','target':target,'snapshot':{'title':f'{m["chat_name"]} · {name} · {r["created_at"]}', 'provider_revision':None, 'captured_at':r['observed_at'],'capture_scope':{'kind':'whole_resource'},'extraction_profile':'feishu-message-v1','body':{'format':'text','text':text or '[无文本消息]'},'provenance':{'method':'lark-cli-message','reported_by':name}},'advance_head':True,'reason':'保存群消息原文与来源身份'}
        # Reuse the original payload after a response loss, including its former append base.
        key='capture_'+vid
        oldstep=self.db.execute('SELECT request_json FROM monitor_steps WHERE run_id=? AND step_key=?',(run['id'],key)).fetchone()
        if oldstep:payload=json.loads(oldstep['request_json'])
        result=self.step(pid,{**selected,'step_key':key,'command':'source.import','input':payload})
        snapshot=result['data']['snapshot_id']
        with self.transaction():
            self.guard(pid,p);self.db.execute('UPDATE monitor_messages SET source_version_id=? WHERE id=?',(snapshot,vid))
        return {'source_version_id':snapshot,'source_id':result['data']['source_id'],'change_id':result['meta']['change_id']}
    def capture_segment(self,pid,p):
        if 'message_version' in p or not isinstance(p.get('title'),str) or not p['title'].strip():
            raise YuError('INVALID_INPUT','讨论片段需要 title 与 message_versions，不同时接受 message_version。')
        run,m,rows=self.selected(pid,p)
        rows.sort(key=lambda r:(r['created_at'],r['message_id'],r['version']))
        if len({r['message_id'] for r in rows})!=len(rows):
            raise YuError('INVALID_INPUT','同一讨论片段不能混入同一消息的多个版本。')
        ids=[r['id'] for r in rows]
        membership=sorted(r['message_id'] for r in rows)
        key=f'{m["identity"]}:segment_{digest(membership)[:32]}:{m["chat_id"]}:{membership[0]}'
        from .source import _remote_identity
        def location(row):
            target={'provider':'feishu','resource_type':'chat_segment','provider_key':key,'canonical_url':row['message'].get('message_app_link')}
            if isinstance(target['canonical_url'],str):
                try:return _remote_identity(target)[1]
                except YuError:pass
            return m['chat_url']
        old=self.db.execute("SELECT id,latest_snapshot_id FROM sources WHERE project_id=? AND provider='feishu' AND resource_type='chat_segment' AND provider_key=?",(pid,key)).fetchone()
        target={'mode':'append','source_id':old['id'],'base_snapshot_id':old['latest_snapshot_id']} if old else {
            'mode':'create','provider':'feishu','resource_type':'chat_segment','provider_key':key,'canonical_url':location(rows[0])}
        parts=[p['title'].strip(), f'群聊：{m["chat_name"]}',
               f'片段范围（UTC）：{rows[0]["created_at"]} — {rows[-1]["created_at"]}',
               '以下为所选讨论片段的原始消息，不代表完整群历史。']
        for row in rows:
            msg=row['message'];sender=msg.get('sender',{})
            name=sender.get('name') or sender.get('id') or '未知发言者' if isinstance(sender,dict) else str(sender)
            text=msg.get('content','');text=text if isinstance(text,str) else canonical(text)
            parts.extend(['',f'{name} · {msg.get("create_time",row["created_at"])}',
                          f'出处：{location(row)}',('[消息已撤回]\n' if msg.get('deleted') else '')+(text or '[无文本消息]')])
        payload={'api_version':'1','command':'source.import','target':target,
                 'snapshot':{'title':p['title'].strip(),'provider_revision':None,'captured_at':max(r['observed_at'] for r in rows),
                             'capture_scope':{'kind':'whole_resource'},'extraction_profile':'feishu-chat-segment-v1',
                             'body':{'format':'text','text':'\n'.join(parts)},'provenance':{'method':'lark-cli-chat-segment'}},
                 'advance_head':True,'reason':'保存有上下文的项目讨论片段'}
        step_key='segment_'+digest(ids)[:48]
        oldstep=self.db.execute('SELECT request_json,result_json FROM monitor_steps WHERE run_id=? AND step_key=?',(run['id'],step_key)).fetchone()
        if oldstep:
            original=json.loads(oldstep['request_json'])
            if original['snapshot']['title']!=p['title'].strip():raise YuError('IDEMPOTENCY_CONFLICT','同一片段重试需保留原 title。')
            payload=original
        result=self.step(pid,{**p,'message_versions':ids,'step_key':step_key,'command':'source.import','input':payload})
        snapshot=result['data']['snapshot_id']
        with self.transaction():
            self.guard(pid,p)
            for vid in ids:self.db.execute('UPDATE monitor_messages SET source_version_id=? WHERE id=?',(snapshot,vid))
        return {'source_version_id':snapshot,'source_id':result['data']['source_id'],
                'change_id':result['meta']['change_id'],'message_versions':ids,'reused':bool(oldstep and oldstep['result_json']) or result['meta']['replayed']}

    def resolve(self,pid,p):
        outcome=p.get('outcome');reason=p.get('reason')
        if outcome not in ('applied','no_change','clarification') or not isinstance(reason,str) or not reason.strip():raise YuError('INVALID_INPUT','需要明确处置 outcome 与 reason。')
        with self.transaction():
            run,m,rows=self.selected(pid,p)
            first=self.pending(pid,{**p,'limit':len(rows)})['messages']
            if {r['id'] for r in first}!={r['id'] for r in rows}:raise YuError('INVALID_INPUT','必须先完成更早消息，再推进后续理解。')
            if outcome!='no_change':
                changes=p.get('change_ids',[])
                if not isinstance(changes,list) or not changes:raise YuError('INVALID_INPUT','采用或待澄清处置需要实际 draft.apply 回执。')
                for vid in p['message_versions']:
                    covered=False
                    for step in self.db.execute("SELECT * FROM monitor_steps WHERE run_id=? AND command='draft.apply' AND result_json IS NOT NULL",(run['id'],)):
                        result=json.loads(step['result_json'])
                        if vid in json.loads(step['message_versions_json']) and result.get('meta',{}).get('change_id') in changes and result.get('meta',{}).get('change_id'):covered=True
                    if not covered:raise YuError('INVALID_INPUT','消息缺少对应的实际 draft 写入回执。')
            for r in rows:self.db.execute('UPDATE monitor_messages SET disposition=?,reason=?,resolved_run_id=? WHERE id=?',(outcome,reason,run['id'],r['id']))
        return {'resolved':len(rows),'outcome':outcome}
    def finish(self,pid,p):
        with self.transaction():
            run,m=self.guard(pid,p)
            if not run['fetch_complete'] or self.db.execute('SELECT 1 FROM monitor_messages WHERE monitor_id=? AND disposition IS NULL',(m['id'],)).fetchone():raise YuError('MONITOR_INCOMPLETE','尚有未拉取或未处置消息。')
            if self.db.execute('SELECT 1 FROM monitor_steps WHERE run_id=? AND result_json IS NULL',(run['id'],)).fetchone():raise YuError('MONITOR_INCOMPLETE','有未完成的业务步骤；继续原请求。')
            affected=set()
            for row in self.db.execute("SELECT result_json FROM monitor_steps WHERE run_id=? AND command='draft.apply'",(run['id'],)):
                affected.update(v['object_id'] for v in json.loads(row[0]).get('data',{}).get('affected_reviews',[]))
            stale=[v for v in affected_objects(self.db,pid)['review'] if v['object_id'] in affected]
            if stale:raise YuError('MONITOR_REVIEW_PENDING','已写入 draft，相关 review 尚未同步。',details=stale)
            summary=p.get('summary','本轮群消息已处理。')
            if not isinstance(summary,str) or len(summary)>2000:raise YuError('INVALID_INPUT','summary 最多 2000 字符。')
            stamp=now();self.db.execute("UPDATE monitor_runs SET status='complete',completed_at=?,summary=? WHERE id=?",(stamp,summary,run['id']))
            self.db.execute('UPDATE chat_monitors SET last_completed_at=?,last_summary=?,last_error=NULL,next_due_at=? WHERE id=?',(stamp,summary,shifted(run['window_end'],m['interval_minutes']*60),m['id']))
            self.db.execute('DELETE FROM monitor_leases WHERE project_id=?',(pid,))
        return {'completed':True,'run_id':run['id'],'summary':summary}
