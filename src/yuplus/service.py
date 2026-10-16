"""Manage only Yu+ processes with matching directory, PID and instance identity."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import threading
import uuid
from urllib.request import build_opener, ProxyHandler
from .core import YuError, canonical


def status(data_dir):
    root=Path(data_dir).expanduser().resolve(); state=root/'service.json'
    try:
        saved=json.loads(state.read_text())
        port=saved['port']
        if type(port) is not int or not 0<port<65536: raise ValueError()
        with build_opener(ProxyHandler({})).open(f'http://127.0.0.1:{port}/api/health',timeout=2) as r: health=json.load(r)
        if health.get('mode')!='live' or health.get('data_dir')!=str(root) or not saved.get('instance_id') or health.get('instance_id')!=saved['instance_id'] or health.get('pid')!=saved['pid']:
            raise ValueError()
        return {'running':True,**health}
    except (OSError,ValueError,KeyError,TypeError): return {'running':False,'data_dir':str(root)}


def control(data_dir,action):
    root=Path(data_dir).expanduser().resolve()
    if action=='status':return status(root)
    if action=='stop' and not root.exists():return status(root)
    root.mkdir(parents=True,exist_ok=True)
    with (root/'service.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        current=status(root)
        if action=='stop':
            if not current['running']:return current
            os.kill(current['pid'],signal.SIGTERM)
            for _ in range(40):
                if not status(root)['running']:return {'running':False,'data_dir':str(root),'stopped':True}
                time.sleep(.1)
            raise YuError('IO_FAILURE','服务未及时退出，未强制终止。')
        if current['running']:return {**current,'reused':True}
        token=uuid.uuid4().hex
        env={**os.environ,'YUPLUS_SERVICE_INSTANCE':token}
        with (root/'service.log').open('ab') as log:
            child=subprocess.Popen([sys.executable,'-m','yuplus','--data-dir',str(root),'serve','--port','0','--json'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
        for _ in range(100):
            current=status(root)
            if current['running'] and current['instance_id']==token:
                threading.Thread(target=child.wait,daemon=True).start()
                return {**current,'reused':False}
            if child.poll() is not None:break
            time.sleep(.1)
        if child.poll() is None: child.terminate();child.wait(timeout=5)
        raise YuError('IO_FAILURE','服务启动失败，请检查数据目录中的 service.log。')


def register(server):
    token=os.environ.get('YUPLUS_SERVICE_INSTANCE')
    if token:
        path=server.data_dir/'service.json'; temp=server.data_dir/('service-'+token+'.tmp')
        temp.write_text(canonical({'port':server.server_port,'pid':os.getpid(),'instance_id':token}))
        temp.replace(path)
