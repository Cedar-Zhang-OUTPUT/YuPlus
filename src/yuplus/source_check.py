"""Observation-only remote scanning; no source content or object rewrites."""
import json
import sqlite3
from .app import App
from .core import YuError, canonical, now
from .feishu import observe


def scan(data_dir, project_id=None, source_id=None, observer=observe):
    app=App(data_dir)
    try:
        if project_id: app._project(project_id)
        if source_id and not project_id: raise YuError('INVALID_INPUT','指定来源时必须指定项目。')
        clauses=["provider='feishu'","archived_at IS NULL"]
        values=[]
        if project_id: clauses.append('project_id=?');values.append(project_id)
        if source_id: clauses.append('id=?');values.append(source_id)
        sources=[dict(r) for r in app.db.execute('SELECT * FROM sources WHERE '+' AND '.join(clauses)+' ORDER BY project_id,id',values)]
        if source_id and not sources: raise YuError('SOURCE_NOT_FOUND','未找到可检查的飞书来源。')
        results=[]
        for source in sources:
            head=source['latest_snapshot_id']; generation=source['observation_generation']
            snapshot=app.db.execute('SELECT provider_revision,provenance_json FROM source_versions WHERE project_id=? AND id=?',(source['project_id'],head)).fetchone()
            observation=None;error=None
            try:
                remote=observer(source)
                previous=json.loads(source['remote_observation_json'] or '{}')
                baseline=snapshot['provider_revision'] if snapshot and remote['kind']=='revision' else (json.loads(snapshot['provenance_json']).get('remote_marker') if snapshot else None)
                conclusion='unknown'
                if baseline is not None:
                    conclusion='unchanged' if str(baseline)==remote['marker'] else 'changed'
                elif previous.get('basis_snapshot_id')==head and previous.get('kind')==remote['kind']:
                    # With no capture-time marker, matching an earlier observation does not prove content parity.
                    conclusion='changed' if previous.get('marker')!=remote['marker'] or previous.get('conclusion')=='changed' else 'unknown'
                observation={**remote,'basis_snapshot_id':head,'conclusion':conclusion,'observed_at':now(),
                    'method':'文档 revision' if remote['kind']=='revision' else '资源修改时间',
                    'detail':f"收录基线：{baseline if baseline is not None else '未记录'}；远端：{remote['marker']}"}
            except YuError as exc:
                error={'code':exc.code,'message':exc.message,'at':now()}
            checked=now()
            app.db.execute('BEGIN IMMEDIATE')
            try:
                result=app.db.execute('''UPDATE sources SET remote_observation_json=COALESCE(?,remote_observation_json),check_error_json=?,last_checked_at=?,observation_generation=observation_generation+1
                    WHERE project_id=? AND id=? AND latest_snapshot_id IS ? AND observation_generation=?''',
                    (canonical(observation) if observation else None,canonical(error) if error else None,checked,source['project_id'],source['id'],head,generation))
                app.db.execute('COMMIT')
            except BaseException:app.db.execute('ROLLBACK');raise
            results.append({'project_id':source['project_id'],'source_id':source['id'],'applied':result.rowcount==1,'observation':observation,'error':error,'checked_at':checked})
        return {'checks':results,'changed':sum(r['applied'] and (r['observation'] or {}).get('conclusion')=='changed' for r in results),'errors':sum(r['error'] is not None for r in results)}
    finally: app.close()


def startup_scan(data_dir):
    # Worker owns its SQLite connection; failures do not prevent local browsing.
    try: scan(data_dir)
    except (YuError,OSError,ValueError,sqlite3.Error): pass
