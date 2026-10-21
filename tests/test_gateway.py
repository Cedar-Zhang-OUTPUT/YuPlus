"""Real persisted CLI data through the loopback HTTP boundary."""
import copy
import http.client
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from yuplus.app import App
from yuplus.browser_view import browser_view, read_snapshot
from yuplus.gateway import GatewayServer


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        self.app = App(self.data)
        self.addCleanup(self.app.close)
        self.pid = self.app.execute('project.create', {'name': '真实项目'}, request_id='req_one')['data']['project_id']
        self.other = self.app.execute('project.create', {'name': '其他项目'}, request_id='req_other')['data']['project_id']
        self.server = GatewayServer(self.data, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.counter = 0

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def request(self, path, method='GET', headers=None, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request(method, path, headers=headers or {}, body=body)
        response = connection.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        connection.close()
        return result

    def view(self, pid=None):
        status, _, body = self.request('/api/view' + ('?' + urlencode({'project': pid}) if pid else ''))
        self.assertEqual(status, 200, body)
        return json.loads(body)

    def execute(self, command, payload, pid=None):
        self.counter += 1
        return self.app.execute(command, payload, project_id=pid or self.pid, request_id=f'req_{self.counter}')['data']

    def source(self, storage='copy', mime='text/plain', pid=None):
        path = self.root / f'material{self.counter}.txt'
        path.write_bytes(b'saved material bytes')
        request = {'api_version':'1','command':'source.import','target':{'mode':'create','provider':'local','resource_type':'file','provider_key':f'material_{self.counter}'},
            'snapshot':{'title':'保存原文','provider_revision':None,'captured_at':'2026-10-13T02:00:00Z','capture_scope':{'kind':'whole_resource'},
              'extraction_profile':'verbatim-v1','body':{'format':'text','text':'来源正文'},'provenance':{'method':'test'},
              'assets':[{'asset_id':'asset_original','role':'original','display_name':'材料.txt','mime_type':mime,'local_path':str(path),'storage':storage}]},
            'advance_head':True,'reason':'导入材料'}
        return self.execute('source.import', request, pid), path

    def draft(self, text='初版', old=None):
        target = {'op_id':'delivery', 'type_key':'deliverables', 'scope_key':'project'}
        if old: target['object_id'] = old['object_id']
        obj = {**target,'base_revision':old['revision_id'] if old else None,
               'set_items':[{'item_id':'item_changed','data':{'deliverable':text},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]},
                            {'item_id':'item_stable','data':{'deliverable':'不变'},'epistemic_kind':'hypothesis','source_refs':[],'dependencies':[]}]}
        return self.execute('draft.apply', {'api_version':'1','command':'draft.apply','reason':'修改交付','objects':[obj],'decisions':[]})['objects'][0]

    def test_global_and_selected_project_contract(self):
        own, _ = self.source()
        other, _ = self.source(pid=self.other)
        global_view = self.view()
        self.assertEqual(len(global_view['projects']), 2)
        self.assertFalse(global_view['sources'])
        view = self.view(self.pid)
        self.assertFalse(view['meta']['demo'])
        self.assertEqual(view['meta']['project_id'], self.pid)
        self.assertEqual([s['id'] for s in view['sources']], [own['source_id']])
        self.assertNotIn(other['source_id'], json.dumps(view['source_versions']))
        self.assertEqual(view['source_versions'][0]['capture_scope']['mode'], 'all')
        self.assertEqual(view['source_versions'][0]['body_text'], '来源正文')
        status, _, raw = self.request('/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['data_dir'], str(self.data.resolve()))
        self.assertEqual(self.request('/api/view?project=missing')[0], 404)

    def test_item_basis_history_and_authoritative_status(self):
        initial = self.draft()
        deps = [{'dependency_id':f'dep_{item}', 'object_id':initial['object_id'],'revision_id':initial['revision_id'],'item_id':item,'kind':'fact'} for item in ['item_changed','item_stable']]
        review = self.execute('review.publish', {'api_version':'1','command':'review.publish','reason':'生成成果', 'documents':[{
            'target':{'type_key':'debrief','scope_key':'project'},'base_revision':None,
            'read_basis':[{'object_id':initial['object_id'],'revision_id':initial['revision_id']}], 'structure_cause_change_ids':[],
            'set_blocks':[{'block_id':f'block_{i}','markdown':'已采用','dependencies':[dep],'cause_change_ids':[]} for i, dep in enumerate(deps)]}]})['documents'][0]
        self.draft('新版', initial)
        view = self.view(self.pid)
        self.assertEqual(len(view['object_revisions']), 3)
        statuses = view['basis_status_by_key']
        self.assertEqual(statuses[f"{initial['object_id']}:{initial['revision_id']}:item_changed"], 'changed')
        self.assertEqual(statuses[f"{initial['object_id']}:{initial['revision_id']}:item_stable"], 'same')
        revision = next(r for r in view['object_revisions'] if r['id'] == review['revision_id'])
        self.assertEqual(revision['block_lineage']['block_0']['basis'][0]['revision_id'], initial['revision_id'])
        self.assertEqual(revision['payload']['blocks'][1]['dependencies'][0]['status'], 'same')

    def test_asset_ranges_integrity_and_project_isolation(self):
        imported, original = self.source()
        asset = self.view(self.pid)['source_versions'][0]['assets'][0]
        original.write_bytes(b'changed original')
        status, headers, body = self.request(asset['url'], headers={'Range':'bytes=2-6'})
        self.assertEqual((status, body), (206, b'ved m'))
        self.assertEqual(headers['Content-Range'], 'bytes 2-6/20')
        self.assertEqual(self.request(asset['url'], headers={'Range':'bytes=500-600'})[0], 416)
        self.assertEqual(self.request(asset['url'].replace(self.pid, self.other))[0], 404)
        external, path = self.source(storage='external')
        view = self.view(self.pid)
        ext = next(v for v in view['source_versions'] if v['id'] == external['snapshot_id'])['assets'][0]
        path.write_bytes(b'different')
        self.assertEqual(self.request(ext['url'])[0], 409)
        self.assertEqual(next(v for v in self.view(self.pid)['source_versions'] if v['id'] == external['snapshot_id'])['assets'][0]['availability'], 'changed')
        copied = self.data / 'objects' / asset['storage_key']
        copied.unlink(); copied.symlink_to(path)
        self.assertEqual(self.request(asset['url'])[0], 409)

    def test_exact_snapshot_evidence_and_read_only_connection(self):
        original, _ = self.source()
        op = {'op_id':'brief','type_key':'client_brief','scope_key':'project','base_revision':None,
            'set_items':[{'item_id':'requirement','data':{'requirement':'已保存要求'},'epistemic_kind':'source_statement',
                'source_refs':[{'evidence_id':'ev','source_version_id':original['snapshot_id'],'asset_id':'asset_original','kind':'quote','locator':{'paragraph':'1'}}], 'dependencies':[]}]}
        self.execute('draft.apply', {'api_version':'1','command':'draft.apply','reason':'整理原文','objects':[op],'decisions':[]})
        self.execute('source.import', {'api_version':'1','command':'source.import',
            'target':{'mode':'append','source_id':original['source_id'],'base_snapshot_id':original['snapshot_id']},
            'snapshot':{'title':'新标题','provider_revision':None,'captured_at':'2026-10-14T02:00:00Z',
                'capture_scope':{'kind':'whole_resource'},'extraction_profile':'verbatim-v1','body':{'format':'text','text':'新版正文'},'provenance':{'method':'test'}},
            'advance_head':True,'reason':'更新来源'})
        view = self.view(self.pid)
        self.assertEqual(len(view['source_versions']), 2)
        self.assertEqual(view['sources'][0]['cached_title'], '新标题')
        ref = view['object_revisions'][0]['payload']['items'][0]['source_refs'][0]
        self.assertEqual(ref['evidence_kind'], 'quote')
        self.assertEqual(ref['source_version_id'], original['snapshot_id'])
        old = next(v for v in view['source_versions'] if v['id'] == ref['source_version_id'])
        self.assertEqual(old['title_at_capture'], '保存原文')
        self.assertEqual(old['body_text'], '来源正文')
        with read_snapshot(self.data) as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('UPDATE projects SET name=? WHERE id=?', ('wrong', self.pid))

    def test_active_content_is_download_only(self):
        self.source(mime='text/html')
        asset = self.view(self.pid)['source_versions'][0]['assets'][0]
        status, headers, _ = self.request(asset['url'])
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'application/octet-stream')
        self.assertTrue(headers['Content-Disposition'].startswith('attachment'))
        self.assertIn('sandbox', headers['Content-Security-Policy'])

    def test_download_preserves_file_bytes_and_name_without_changing_inline_open(self):
        self.source(mime='image/jpeg')
        asset = self.view(self.pid)['source_versions'][0]['assets'][0]
        status, headers, body = self.request(asset['url'] + '&download=1')
        self.assertEqual(status, 200)
        self.assertEqual(body, b'saved material bytes')
        self.assertEqual(headers['Content-Disposition'], "attachment; filename*=UTF-8''%E6%9D%90%E6%96%99.txt")
        self.assertTrue(self.request(asset['url'])[1]['Content-Disposition'].startswith('inline'))
        self.assertEqual(self.request(asset['url'] + '&download=anything')[0], 400)
        self.assertEqual(self.request(asset['url'].replace(self.pid, self.other) + '&download=1')[0], 404)

    def test_finder_only_reveals_original_external_files_not_pool_or_restored_files(self):
        copied, _ = self.source()
        external, original = self.source(storage='external')
        headers = {'Origin': self.server.url, 'Content-Type': 'application/json'}
        def reveal(source):
            return self.request('/api/local-files/reveal', 'POST', headers, json.dumps({
                'projectId': self.pid, 'versionId': source['snapshot_id'], 'assetId': 'asset_original'}))[0]
        def files():
            return json.loads(self.request('/api/local-files?project=' + self.pid)[2])['files']
        with patch('yuplus.gateway.sys.platform', 'darwin'), patch('yuplus.gateway.shutil.which', return_value='/usr/bin/open'), patch('yuplus.gateway.subprocess.run') as opened:
            opened.return_value.returncode = 0
            self.assertEqual([f['versionId'] for f in files()], [external['snapshot_id']])
            self.assertEqual(reveal(copied), 400)
            opened.assert_not_called()
            self.assertEqual(reveal(external), 200)
            self.assertEqual(opened.call_args.args[0], ['open', '-R', str(original.resolve())])
            opened.reset_mock()
            asset = next(v for v in self.view(self.pid)['source_versions'] if v['id'] == external['snapshot_id'])['assets'][0]
            restored = self.data/'external-files'/asset['sha256']
            restored.parent.mkdir(); restored.write_bytes(original.read_bytes())
            (self.data/'restored-assets.json').write_text(json.dumps({str(original.resolve()) + ':' + asset['sha256']: 'external-files/' + asset['sha256']}))
            self.assertEqual(files(), [])
            self.assertEqual(reveal(external), 400)
            opened.assert_not_called()
            self.assertEqual(self.request(asset['url'] + '&download=1')[0], 200)

    def test_host_origin_methods_and_traversal_boundaries(self):
        for headers in [{'Host':'evil.example'}, {'Origin':'https://evil.example'}, {'Origin':'null'}, {'Sec-Fetch-Site':'cross-site'}]:
            self.assertEqual(self.request('/api/health', headers=headers)[0], 403)
        self.assertEqual(self.request('/api/view', 'POST')[0], 405)
        self.assertEqual(self.request('/api/health', 'DELETE')[0], 405)
        self.assertEqual(self.request('/%2e%2e/pyproject.toml')[0], 403)
        self.assertEqual(self.request('/api/local-files/reveal', 'POST', {'Content-Type':'application/json'}, '{}')[0], 403)
        headers = {'Content-Type':'application/json','Origin':self.server.url}
        self.assertEqual(self.request('/api/local-files/reveal', 'POST', headers, json.dumps({'path':'/etc/passwd'}))[0], 400)
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/api/view?project=a&project=b')[0], 400)

    def test_health_does_not_initialize_missing_database(self):
        self.server.data_dir = self.root / 'missing'
        self.assertEqual(self.request('/api/health')[0], 503)
        self.assertFalse(self.server.data_dir.exists())

    def test_cli_serve_reports_actual_port_and_stops(self):
        process = subprocess.Popen([sys.executable, '-m', 'yuplus', '--data-dir', str(self.root/'cli-data'), 'serve', '--port', '0', '--json'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = process.stdout.readline()
            result = json.loads(line)
            self.assertTrue(result['ok'], result)
            self.assertGreater(result['data']['port'], 0)
            self.assertEqual(result['data']['data_dir'], str((self.root/'cli-data').resolve()))
            process.send_signal(signal.SIGINT)
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None: process.kill(); process.wait()
            process.stdout.close(); process.stderr.close()
