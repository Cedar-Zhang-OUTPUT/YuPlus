"""Source preference writes, upgrade preservation and research filtering."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from yuplus.app import App
from yuplus.case_library import _DEFAULTS, _DEFAULT_RECEIPT, _LEGACY_RECEIPT, catalog
from yuplus.gateway import GatewayServer


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.data = Path(temp.name) / 'data'
        self.app = App(self.data); self.addCleanup(self.app.close)
        self.server = GatewayServer(self.data, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.stop)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def post(self, action, fields, request_id='ui_test', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        body = json.dumps({'action': action, 'input': fields, 'request_id': request_id})
        conn.request('POST', '/api/libraries', body, headers if headers is not None else {'Origin': self.origin, 'Content-Type': 'application/json'})
        response = conn.getresponse(); result = (response.status, json.loads(response.read())); conn.close(); return result

    def test_defaults_disable_restore_personal_replay_and_restart(self):
        before = catalog(self.app.db)
        self.assertEqual(len(before), 31)
        self.assertTrue(all(r['origin'] == 'official' and r['enabled'] for r in before))
        self.assertFalse(any('milanote' in r['url'] for r in before))
        row = before[0]
        payload = {'library_id': row['id'], 'base_version': row['version']}
        status, result = self.post('delete', payload)
        self.assertEqual(status, 200)
        self.assertEqual(len(result['libraries']), 31)
        self.assertFalse(next(r for r in result['libraries'] if r['id'] == row['id'])['enabled'])
        self.assertEqual(len(self.app.execute('library.list')['data']['libraries']), 30)
        self.assertTrue(self.post('delete', payload)[1]['meta']['replayed'])
        self.assertEqual(self.post('restore', payload, 'stale')[0], 409)
        reopened = App(self.data)
        try:self.assertFalse(next(r for r in catalog(reopened.db) if r['id'] == row['id'])['enabled'])
        finally:reopened.close()
        self.assertEqual(self.post('restore', {**payload, 'base_version': 2}, 'restore')[0], 200)
        status, result = self.post('add', {'name': 'Personal', 'kind': 'website', 'url': 'https://example.com/', 'description':'互动体验', 'search_guidance':'先看视频'}, 'personal')
        self.assertEqual(status, 200)
        own = next(r for r in result['libraries'] if r['name'] == 'Personal')
        self.assertEqual(own['origin'], 'personal'); self.assertTrue(own['enabled'])
        status, updated = self.post('update', {'library_id':own['id'], 'base_version':1, 'name':own['name'], 'url':own['url'], 'description':'', 'search_guidance':'核对年份'}, 'edit')
        self.assertEqual(status,200)
        self.assertEqual(updated['data']['search_guidance'],'核对年份')
        cli = self.app.execute('library.show',{'library_id':own['id']})['data']
        self.assertEqual(cli['description'],''); self.assertEqual(cli['search_guidance'],'核对年份')
        self.assertEqual(self.post('add', {'name': 'Duplicate', 'kind': 'website', 'url': 'https://example.com/'}, 'duplicate')[0], 409)
        for table in ('projects', 'sources', 'objects', 'blobs'):
            self.assertEqual(self.app.db.execute(f'SELECT count(*) FROM {table}').fetchone()[0], 0)

    def test_writes_require_same_origin_and_narrow_payload(self):
        payload = {'name': 'Personal', 'kind': 'website', 'url': 'https://example.com/'}
        for headers in [{}, {'Origin': 'https://evil.example', 'Content-Type': 'application/json'},
                        {'Origin': self.origin, 'Content-Type': 'text/plain'},
                        {'Origin': self.origin, 'Content-Type': 'application/json', 'Sec-Fetch-Site': 'cross-site'}]:
            self.assertIn(self.post('add', payload, headers=headers)[0], (400, 403))
        for action, fields in [('purge', payload), ('update', payload), ('add', {**payload, 'origin': 'official'}),
                               ('add', {**payload, 'url': 'javascript:alert(1)'}), ('add', {**payload, 'body': 'content'})]:
            self.assertEqual(self.post(action, fields)[0], 400)
        self.assertEqual(len(catalog(self.app.db)), 31)

    def test_v1_upgrade_only_adds_new_batch_and_retains_provenance(self):
        legacy = self.data.parent / 'legacy'
        manifest = json.loads(_DEFAULTS.read_text())
        old_manifest = self.data.parent / 'v1.json'
        old_manifest.write_text(json.dumps({'libraries': manifest['libraries'][:18]}))
        with patch('yuplus.case_library._DEFAULTS', old_manifest), patch('yuplus.case_library._DEFAULT_RECEIPT', _LEGACY_RECEIPT):
            old = App(legacy)
        rows = old.execute('library.list')['data']['libraries']
        first, second = rows[:2]
        old.execute('library.delete', {'api_version': '1', 'command': 'library.delete', 'library_id': first['id'], 'base_version': 1}, request_id='disabled')
        old.execute('library.update', {'api_version': '1', 'command': 'library.update', 'library_id': second['id'], 'base_version': 1,
                    'name': 'Edited source', 'kind': 'website', 'url': 'https://example.org/edited'}, request_id='edited')
        old.close()
        upgraded = App(legacy)
        try:
            rows = catalog(upgraded.db)
            self.assertEqual(len(rows), 31)
            self.assertEqual(sum(r['enabled'] for r in rows), 30)
            self.assertTrue(all(r['origin'] == 'official' for r in rows))
            self.assertEqual(next(r for r in rows if r['id'] == second['id'])['url'], 'https://example.org/edited')
            self.assertEqual(upgraded.db.execute('SELECT count(*) FROM case_library_requests WHERE request_id=?', (_DEFAULT_RECEIPT,)).fetchone()[0], 1)
        finally:upgraded.close()
