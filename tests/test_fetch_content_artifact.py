"""Local zero-network acceptance for the private APEX artifact consumer."""
import importlib.util
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('fetch_content_artifact', HERE.parent/'scripts'/'fetch_content_artifact.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.endswith('/redirect.mp4'):
            self.send_response(302)
            self.send_header('Location', 'https://example.org/stolen')
            self.end_headers()
            return
        if self.path.endswith('/manifest.json'):
            if self.headers.get('Authorization') != 'Bearer test-token':
                self.send_response(401)
                self.end_headers()
                return
            body = b'{"job":"test"}'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


class ArtifactClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.http.server_port}'
        self.environ = patch.dict(os.environ, {'CONTENT_ARTIFACT_TOKEN':'test-token'})
        self.environ.start()

    def tearDown(self):
        self.environ.stop()
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def fetch(self, **kwargs):
        return client.retrieve('safe-job', 'manifest.json', self.dir/'manifest.json', base_url=self.url, **kwargs)

    def test_authorized_fetch_with_known_digest(self):
        # Exercise correct pre-recorded hash, rather than guessing it.
        import hashlib
        expected = hashlib.sha256(b'{"job":"test"}').hexdigest()
        path, actual = self.fetch(expected_sha256=expected)
        self.assertEqual(path.read_bytes(), b'{"job":"test"}')
        self.assertEqual(actual, expected)
        self.assertFalse(any(self.dir.glob('.apex-artifact-*')))

    def test_bad_digest_does_not_leave_artifact(self):
        with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
            self.fetch(expected_sha256='0'*64)
        self.assertFalse((self.dir/'manifest.json').exists())

    def test_no_token_denies_before_request(self):
        with patch.dict(os.environ, {'CONTENT_ARTIFACT_TOKEN': ''}):
            with self.assertRaisesRegex(ValueError, 'missing'):
                self.fetch()

    def test_invalid_token_denied(self):
        with patch.dict(os.environ, {'CONTENT_ARTIFACT_TOKEN': 'invalid'}):
            with self.assertRaisesRegex(ValueError, 'HTTP 401'):
                self.fetch()

    def test_existing_destination_not_overwritten(self):
        target = self.dir/'manifest.json'
        target.write_text('preserve')
        with self.assertRaises(FileExistsError):
            self.fetch()
        self.assertEqual(target.read_text(), 'preserve')

    def test_unsafe_job_and_artifact_rejected(self):
        for job in ['../etc', 'a', 'foo/bar', 'abc?x=1']:
            with self.assertRaises(ValueError):
                client.retrieve(job,'manifest.json',self.dir/'out',base_url=self.url)
        with self.assertRaises(ValueError):
            client.retrieve('safe-job','../../secret',self.dir/'out',base_url=self.url)

    def test_unapproved_origin_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unapproved download origin'):
            client.retrieve('safe-job','manifest.json',self.dir/'out',base_url='https://malicious.example')

    def test_stream_limit_no_partial_file(self):
        with patch.object(client, 'MAX_BYTES', 5):
            with self.assertRaisesRegex(ValueError, 'download limit'):
                self.fetch()
        self.assertFalse((self.dir/'manifest.json').exists())
        self.assertFalse(any(self.dir.glob('.apex-artifact-*')))

    def test_redirect_handler_refuses_to_forward_credentials(self):
        from urllib.request import Request, build_opener
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as error:
            build_opener(client.NoRedirects()).open(Request(self.url+'/redirect.mp4',headers={'Authorization':'Bearer test-token'}))
        self.assertEqual(error.exception.code,302)


if __name__ == '__main__':
    unittest.main()
