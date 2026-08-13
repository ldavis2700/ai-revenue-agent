import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from scripts import inbound_server


class InboundServerTests(unittest.TestCase):
    def setUp(self):
        inbound_server.ALLOWED_ORIGINS.clear()
        inbound_server.ALLOWED_ORIGINS.add('https://offer.example')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), inbound_server.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def post(self, origin, payload):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request('POST', '/leads', json.dumps(payload), {
            'Origin': origin, 'Content-Type': 'application/json'})
        response = conn.getresponse()
        body = json.loads(response.read())
        conn.close()
        return response.status, body

    def test_rejects_unknown_origin(self):
        status, body = self.post('https://bad.example', {'email': 'owner@example.com'})
        self.assertEqual(status, 403)
        self.assertEqual(body['errors'], ['origin_not_allowed'])

    def test_accepts_consented_lead(self):
        payload = {'email': 'owner@example.com', 'company': 'Example Co',
                   'contact_consent': True, 'privacy_acknowledged': True}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(inbound_server, 'record_intake') as record:
                status, body = self.post('https://offer.example', payload)
                self.assertEqual(status, 202)
                self.assertTrue(body['accepted'])
                record.assert_called_once()


if __name__ == '__main__':
    unittest.main()
