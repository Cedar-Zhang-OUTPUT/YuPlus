import http.client
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import zlib

from yuplus.app import App
from yuplus.appearance import PNG, chunk, normalize_png, image_bytes
from yuplus.backup import create_backup, restore_backup
from yuplus.core import YuError
from yuplus.gateway import GatewayServer


def png(width=4, height=3, note=True):
    return PNG + chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0)) + (chunk(b'tEXt',b'Comment\0private metadata') if note else b'') + chunk(b'IDAT',zlib.compress((b'\0'+b'\x22\x88\xee\x80'*width)*height)) + chunk(b'IEND',b'')


class LogoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'data'
        self.app=App(self.data);self.addCleanup(self.app.close)
        self.file=self.root/'avatar.png';self.file.write_bytes(png())

    def apply(self, version=0, request='req_logo', command='logo.set'):
        payload={'api_version':'1','command':command,'base_version':version}
        if command=='logo.set':payload['local_path']=str(self.file)
        return self.app.execute(command,payload,request_id=request)

    def test_set_replay_conflict_reset(self):
        self.assertEqual(self.app.execute('logo.show')['data']['version'],0)
        saved=self.apply();self.assertTrue(saved['data']['custom'])
        self.assertEqual(saved['data']['version'],1)
        self.assertNotIn(b'private metadata',image_bytes(self.app.db))
        self.assertEqual(self.file.read_bytes(),png())
        self.file.unlink()
        self.assertTrue(self.apply()['meta']['replayed'])
        with self.assertRaises(YuError) as cm:self.apply(request='req_conflict')
        self.assertEqual(cm.exception.code,'BASE_REVISION_CONFLICT')
        with self.assertRaises(YuError) as cm:self.apply(1,command='logo.reset')
        self.assertEqual(cm.exception.code,'IDEMPOTENCY_CONFLICT')
        reset=self.apply(1,'req_reset','logo.reset')
        self.assertFalse(reset['data']['custom']);self.assertEqual(reset['data']['version'],2)

    def test_bad_images_and_scope_leave_state_unchanged(self):
        for bad in (b'<svg/>',png(513,1),png()[:-2],png()+b'junk',png().replace(b'IHDR',b'BAD!'), b'x'*(256*1024+1)):
            self.file.write_bytes(bad)
            with self.assertRaises(YuError):self.apply()
            self.assertEqual(self.app.execute('logo.show')['data']['version'],0)
        with self.assertRaises(YuError):self.app.execute('logo.show',project_id='prj_abc')
        oversized=PNG+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'*2000000))+chunk(b'IEND',b'')
        with self.assertRaises(YuError):normalize_png(oversized)
        broken=PNG+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',b'not-zlib')+chunk(b'IEND',b'')
        with self.assertRaises(YuError):normalize_png(broken)

    def test_backup_restart_and_restore_keep_logo_and_projects(self):
        pid=self.app.execute('project.create',{'name':'保留项目'},request_id='req_project')['data']['project_id']
        self.apply();expected=image_bytes(self.app.db)
        reopened=App(self.data)
        try:self.assertEqual(image_bytes(reopened.db),expected)
        finally:reopened.close()
        backup=self.root/'backup';create_backup(self.data,backup)
        restored=self.root/'restored';restore_backup(backup,restored)
        app=App(restored)
        try:
            self.assertEqual(image_bytes(app.db),expected)
            self.assertEqual(app.execute('logo.show')['data']['version'],1)
            self.assertEqual(app.execute('project.show',project_id=pid)['data']['name'],'保留项目')
        finally:app.close()

    def test_schema5_migration_makes_backup(self):
        self.app.db.execute('DROP TABLE workspace_logo');self.app.db.execute('DROP TABLE logo_requests');self.app.db.execute('PRAGMA user_version=5')
        upgraded=App(self.data)
        try:self.assertEqual(upgraded.execute('doctor')['data']['schema_version'],10)
        finally:upgraded.close()
        backups=list((self.root/'data-migration-backups').iterdir());self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]/'yuplus.sqlite') as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],5)

    def test_cli_and_read_only_http(self):
        request=self.root/'request.json';request.write_text(json.dumps({'api_version':'1','command':'logo.set','base_version':0,'local_path':str(self.file)}))
        result=subprocess.run([sys.executable,'-m','yuplus','logo','set','--data-dir',str(self.data),'--input',str(request),'--request-id','req_cli','--json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)['data']['custom'])
        server=GatewayServer(self.data,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def get(path,method='GET',headers=None):
            con=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            con.request(method,path,headers=headers or {});res=con.getresponse();data=res.read();code=res.status;mime=res.getheader('Content-Type');con.close();return code,mime,data
        try:
            code,mime,body=get('/api/logo?v=1');self.assertEqual(code,200);self.assertEqual(mime,'image/png');self.assertEqual(body,image_bytes(self.app.db))
            self.assertEqual(get('/api/logo','HEAD')[2],b'')
            view=json.loads(get('/api/view')[2]);self.assertEqual(view['logo']['url'],'/api/logo?v=1');self.assertNotIn('png',view['logo'])
            self.assertEqual(get('/api/logo','POST')[0],405)
            self.assertEqual(get('/api/logo?path=/etc/passwd')[0],400)
            self.assertEqual(get('/api/logo',headers={'Origin':'https://evil.example'})[0],403)
            self.apply(1,'req_reset','logo.reset');self.assertEqual(get('/api/logo')[0],404)
        finally:server.shutdown();server.server_close();thread.join()
