"""The shipped CLI acceptance script must keep working against the actual gateway."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from yuplus.gateway import GatewayServer


class LiveAcceptanceTests(unittest.TestCase):
    def test_real_cli_to_gateway_to_full_export(self):
        scripts=Path(__file__).resolve().parents[1]/'scripts'
        sys.path.insert(0,str(scripts))
        try:
            spec=importlib.util.spec_from_file_location('live_acceptance',scripts/'live_acceptance.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(scripts))
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)
            module.seed(root)
            with GatewayServer(root/'data',0) as server:
                worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
                try:module.finish(root,server.url)
                finally:server.shutdown();worker.join()
            state=json.loads((root/'state.json').read_text())
            manifest=json.loads((root/'export/manifest.json').read_text())
            self.assertEqual(state['phase'],'complete')
            self.assertEqual(len(manifest['review_instances']),5)
            self.assertEqual(len(manifest['shared_qa']),1)
            self.assertTrue(manifest['references_complete'])
            self.assertEqual(manifest['warnings'],[])
            self.assertFalse(manifest['remote_published'])
