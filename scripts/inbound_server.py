#!/usr/bin/env python3
"""Small internal HTTP adapter for consented inbound lead capture."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
try:
    from scripts.capture_inbound_lead import normalize, record_intake
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from capture_inbound_lead import normalize, record_intake

HOST = os.getenv('INBOUND_HOST', '0.0.0.0')
PORT = int(os.getenv('INBOUND_PORT', '8080'))
ALLOWED_ORIGINS = {x.strip() for x in os.getenv('INBOUND_ALLOWED_ORIGINS', '').split(',') if x.strip()}
MAX_BODY_BYTES = 16 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = 'RevenueInbound/1.0'

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        origin = self.headers.get('Origin', '')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        return self.send_json(200, {'ok': True}) if self.path == '/health' else self.send_json(404, {'ok': False})

    def do_OPTIONS(self):
        origin = self.headers.get('Origin', '')
        if origin not in ALLOWED_ORIGINS:
            return self.send_json(403, {'ok': False, 'error': 'origin_not_allowed'})
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Vary', 'Origin')
        self.end_headers()

    def do_POST(self):
        if self.path != '/leads':
            return self.send_json(404, {'accepted': False, 'errors': ['not_found']})
        origin = self.headers.get('Origin', '')
        if ALLOWED_ORIGINS and origin not in ALLOWED_ORIGINS:
            return self.send_json(403, {'accepted': False, 'errors': ['origin_not_allowed']})
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            return self.send_json(413, {'accepted': False, 'errors': ['invalid_body_size']})
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json(400, {'accepted': False, 'errors': ['invalid_json']})
        lead, errors = normalize(payload)
        if errors:
            return self.send_json(422, {'accepted': False, 'errors': errors})
        record_intake(lead)
        return self.send_json(202, {'accepted': True, 'lead_id': lead['id']})

    def log_message(self, fmt, *args):
        return


if __name__ == '__main__':
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
