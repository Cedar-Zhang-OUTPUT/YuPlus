"""Eagle observations: persistence, evidence boundaries, migration and browser reads."""
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from yuplus.app import App
from yuplus.backup import create_backup, restore_backup
from yuplus.browser_view import read_snapshot, browser_view
from yuplus.core import YuError, now
from yuplus.gateway import GatewayServer


class EagleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.data = self.root/'data'
        self.app = App(self.data); self.addCleanup(self.app.close)

    def receipt(self, **changes):
        return dict(api_version='1', command='eagle.record', base_version=0, state='verified',
                    observed_at=now(), server_name='eagle', library_name='品牌案例', library_key='lib_123',
                    tools_listed=True, query_succeeded=True, target_confirmed=True, material_read='thumbnail') | changes

    def test_persist_replay_conflict_failure_and_library_switch(self):
        self.assertEqual(self.app.execute('eagle.status')['data']['version'], 0)
        payload = self.receipt()
        first = self.app.execute('eagle.record', payload, request_id='first')
        again = self.app.execute('eagle.record', payload, request_id='first')
        self.assertEqual(first['data'], again['data']); self.assertTrue(again['meta']['replayed'])
        for value, key in [(payload | {'library_name':'changed'}, 'first'), (payload, 'stale')]:
            with self.assertRaises(YuError): self.app.execute('eagle.record', value, request_id=key)
        failure = self.receipt(base_version=1, state='unavailable', tools_listed=False, query_succeeded=False,
                               target_confirmed=False, material_read='unverified')
        self.app.execute('eagle.record', failure, request_id='failed')
        self.assertEqual(self.app.execute('eagle.status')['data']['material_read'], 'unverified')
        switched = self.receipt(base_version=2, library_name='新库', library_key='lib_456', material_read='original')
        self.app.execute('eagle.record', switched, request_id='switch')
        self.app.execute('eagle.record', payload, request_id='first')  # replay cannot restore old state
        with read_snapshot(self.data) as db:
            record = browser_view(db, self.data)['eagle_connection']
            self.assertEqual(record['library_name'], '新库'); self.assertEqual(record['version'], 3)
        create_backup(self.data, self.root/'backup'); restore_backup(self.root/'backup', self.root/'restored')
        with AppContext(self.root/'restored') as restored:
            self.assertEqual(restored.execute('eagle.status')['data'], record)

    def test_reject_unsupported_evidence_secrets_dates_and_scope(self):
        invalid = [dict(tools_listed=False), dict(query_succeeded=False), dict(target_confirmed=False),
                   dict(material_read='metadata'), dict(library_key=''), dict(server_name=''),
                   dict(endpoint='http://localhost:1234'), dict(token='secret'), dict(library_key='/private/path'),
                   dict(server_name='https://user:password@host'), dict(observed_at='tomorrow'),
                   dict(observed_at='2026-01-01'), dict(observed_at='2999-01-01T00:00:00Z'),
                   dict(query_succeeded=1), dict(state='unavailable'), dict(base_version=True)]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(YuError):
                self.app.execute('eagle.record', self.receipt(**changes), request_id='bad')
        self.assertEqual(self.app.execute('eagle.status')['data']['version'], 0)
        with self.assertRaises(YuError): self.app.execute('eagle.status', project_id='prj_wrong')
        self.app.execute('eagle.record', self.receipt(), request_id='new')
        with self.assertRaises(YuError):
            self.app.execute('eagle.record', self.receipt(base_version=1, observed_at='2000-01-01T00:00:00Z'), request_id='old')

    def test_schema11_upgrade_preserves_preferences_and_backs_up(self):
        old = App(self.root/'legacy')
        pid = old.execute('project.create', {'name':'保留项目'}, request_id='project')['data']['project_id']
        libraries = old.execute('library.list')['data']['libraries']
        old.db.execute('DROP TABLE eagle_connection'); old.db.execute('DROP TABLE eagle_requests')
        old.db.execute('PRAGMA user_version=11'); old.close()
        with AppContext(self.root/'legacy') as upgraded:
            self.assertEqual(upgraded.execute('doctor')['data']['schema_version'], 12)
            self.assertEqual(upgraded.execute('project.show', project_id=pid)['data']['name'], '保留项目')
            self.assertEqual(upgraded.execute('library.list')['data']['libraries'], libraries)
            self.assertEqual(upgraded.execute('eagle.status')['data']['version'], 0)
        backups = list((self.root/'legacy-migration-backups').iterdir())
        self.assertEqual(len(backups), 1)
        with read_snapshot(backups[0]) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 11)

    def test_public_cli_and_http_refresh_are_same_workspace_and_read_only(self):
        env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]/'src')}
        result = subprocess.run([sys.executable, '-m', 'yuplus', '--data-dir', str(self.data), 'eagle',
            'record', '--input', '-', '--request-id', 'cli', '--json'], input=json.dumps(self.receipt()),
            text=True, capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        server = GatewayServer(self.data, 0); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            connection.request('GET', '/api/eagle'); response = connection.getresponse()
            self.assertEqual(response.status, 200); self.assertEqual(json.loads(response.read())['data']['state'], 'verified')
            connection.request('POST', '/api/eagle', body='{}', headers={'Content-Type':'application/json'})
            response = connection.getresponse(); self.assertEqual(response.status, 405); response.read()
            self.app.execute('eagle.record', self.receipt(base_version=1, state='waiting', tools_listed=False,
                query_succeeded=False, target_confirmed=False, material_read='unverified'), request_id='waiting')
            connection.request('GET', '/api/eagle'); response = connection.getresponse()
            self.assertEqual(json.loads(response.read())['data']['state'], 'waiting')
            connection.close()
        finally: server.shutdown(); server.server_close(); thread.join()


class AppContext:
    def __init__(self, path): self.app = App(path)
    def __enter__(self): return self.app
    def __exit__(self, *args): self.app.close()
