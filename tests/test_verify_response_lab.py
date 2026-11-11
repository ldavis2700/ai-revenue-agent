"""No-charge local acceptance tests for the APEX release verifier."""
import importlib.util
from pathlib import Path
import os
import tempfile
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

import content_worker as worker

SPEC = importlib.util.spec_from_file_location(
    'verify_response_lab', Path(__file__).parents[1] / 'scripts' / 'verify_response_lab.py')
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class ReleaseVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.prior = worker.STATE
        worker.STATE = Path(self.temp.name) / 'state'
        worker.initialize()
        with worker.connect() as db:
            db.execute('INSERT INTO health VALUES (1,?)', (worker.time.time(),))
            db.execute("INSERT INTO jobs(id,digest,status,updated,artifact) VALUES ('safe-job','hash','complete',?, 'safe-job')",
                       (worker.time.time(),))
        artifact = worker.STATE / 'artifacts' / 'safe-job'
        artifact.mkdir()
        (artifact / 'manifest.json').write_text('{"id":"safe-job","status":"rendered_unpublished","bytes":4096,"sha256":"' + 'a'*64 + '"}')
        self.env = patch.dict(os.environ, {'CONTENT_ARTIFACT_TOKEN': 'test-content-token'})
        self.env.start()
        self.server = HTTPServer(('127.0.0.1', 0), worker.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.env.stop()
        worker.STATE = self.prior
        self.temp.cleanup()

    def test_complete_private_and_public_read_only_acceptance(self):
        with patch.object(worker, 'reserve_egress', return_value=True):
            result = verifier.inspect(self.origin, job_id='safe-job', token='test-content-token')
        self.assertTrue(result['ready'], result)
        self.assertTrue(all(check['ok'] for check in result['checks'].values()))

    def test_missing_private_token_is_not_a_release_pass(self):
        with patch.dict(os.environ, {'CONTENT_ARTIFACT_TOKEN': ''}):
            with patch.object(worker, 'reserve_egress', return_value=True):
                result = verifier.inspect(self.origin, job_id='safe-job')
        self.assertFalse(result['ready'])
        self.assertFalse(result['checks']['artifact_authorized']['ok'])
        self.assertEqual(result['checks']['artifact_denied']['status'], 503)

    def test_no_private_job_id_is_not_a_release_pass(self):
        with patch.object(worker, 'reserve_egress', return_value=True):
            result = verifier.inspect(self.origin)
        self.assertFalse(result['ready'])
        self.assertEqual(result['checks']['artifact_authorized']['status'], 'not_tested_missing_job_id')

    def test_incomplete_or_invalid_manifest_never_passes_private_acceptance(self):
        artifact = worker.STATE / 'artifacts' / 'safe-job' / 'manifest.json'
        valid = artifact.read_text()
        variations = [
            '{"id":"safe-job","status":"rendered_unpublished"}',
            valid.replace('"bytes":4096', '"bytes":0'),
            valid.replace('"bytes":4096', '"bytes":true'),
            valid.replace('"sha256":"' + 'a'*64 + '"', '"sha256":"invalid"'),
            valid.replace('"rendered_unpublished"', '"queued"'),
        ]
        with patch.object(worker, 'reserve_egress', return_value=True):
            for malformed in variations:
                with self.subTest(manifest=malformed[:80]):
                    artifact.write_text(malformed)
                    result = verifier.inspect(self.origin, job_id='safe-job', token='test-content-token')
                    self.assertFalse(result['ready'], result)
                    self.assertEqual(result['checks']['artifact_authorized']['status'], 200)
                    self.assertFalse(result['checks']['artifact_authorized']['ok'])

    def test_invalid_origin_and_job_fail_before_network(self):
        for origin in ['https://attacker.example', 'http://127.0.0.1:8080@attacker.example']:
            with self.assertRaises(ValueError):
                verifier.inspect(origin, job_id='safe-job', token='test-content-token')
        with self.assertRaises(ValueError):
            verifier.inspect(self.origin, job_id='../unsafe', token='test-content-token')


if __name__ == '__main__':
    unittest.main()
