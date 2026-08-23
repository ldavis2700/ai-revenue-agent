import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from delivery_adapter import deliver, idempotency_key, validate


class Response:
    status = 202


class DeliveryAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "agent.db")
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE events (lead_id TEXT, event_type TEXT, value REAL, metadata TEXT, created_at TEXT)")
        conn.commit()
        conn.close()
        self.action = {
            "lead_id": "in_1",
            "action": "send_initial",
            "email": "buyer@example.com",
            "source": "owned_inbound_opt_in",
            "body": "Thanks for requesting details.",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_external_source_is_blocked(self):
        ok, reason = validate({**self.action, "source": "external"})
        self.assertFalse(ok)
        self.assertEqual(reason, "source_not_verified_owned_inbound")

    def test_key_is_stable(self):
        self.assertEqual(idempotency_key(self.action), idempotency_key(dict(reversed(list(self.action.items())))))

    @patch.dict(os.environ, {
        "DELIVERY_ENABLED": "true",
        "DELIVERY_WEBHOOK_URL": "https://delivery.example.test/send",
        "DELIVERY_WEBHOOK_TOKEN": "secret",
    }, clear=False)
    def test_success_is_recorded_and_duplicate_is_not_resent(self):
        calls = []
        transport = lambda request: calls.append(request) or Response()
        first = deliver(self.action, self.path, transport)
        second = deliver(self.action, self.path, transport)
        self.assertEqual(first["status"], "delivered")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(len(calls), 1)
        conn = sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM events WHERE event_type='sent'").fetchone()[0], 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
