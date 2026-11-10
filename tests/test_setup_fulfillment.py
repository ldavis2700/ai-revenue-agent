import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.setup_fulfillment import delivery_complete, record_delivery
import autonomous_cycle

ROOT = Path(__file__).resolve().parents[1]


class SetupFulfillmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'revenue.db')
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE leads (id TEXT, email TEXT, company TEXT, contact_allowed INTEGER,
                source TEXT, outreach_subject TEXT, outreach_body TEXT);
            CREATE TABLE events (lead_id TEXT,event_type TEXT,metadata TEXT,created_at TEXT);
            CREATE TABLE payment_events (processor_event_id TEXT PRIMARY KEY,lead_id TEXT,
                processor TEXT,amount REAL,created_at TEXT);
            INSERT INTO leads VALUES ('buyer','buyer@example.test','Buyer Co',1,
                'owned_inbound_opt_in','Hello','Preview');
            INSERT INTO payment_events VALUES ('pay1','buyer','provider',100,'2026-01-01T00:00:00Z');
            INSERT INTO events VALUES ('buyer','sale','{"processor_event_id":"pay1"}','2026-01-01T00:00:00Z');
        ''')

    def actions(self):
        self.conn.commit()
        output = subprocess.check_output([sys.executable, str(ROOT / 'scripts/next_actions.py')],
            env={**os.environ, 'REVENUE_DB_PATH': self.path,
                 'MANAGED_CHECKOUT_URL_TEMPLATE': 'https://pay.example.test/managed'}, text=True)
        return json.loads(output)['actions']

    def receipt(self, **overrides):
        args = dict(lead_id='buyer', event_id='pay1', artifact_sha256='a' * 64,
                    evidence_url='https://provider.example.test/deliveries/1',
                    completed_at='2026-01-02T00:00:00Z')
        args.update(overrides)
        return record_delivery(self.conn, **args)

    def test_payment_alone_requires_fulfillment_and_never_claims_completion(self):
        actions = self.actions()
        self.assertEqual(actions[0]['action'], 'fulfill_setup')
        self.assertNotIn('setup is complete', json.dumps(actions))
        self.assertFalse(actions[0]['external_action_allowed'])

    def test_generic_message_delivery_does_not_complete_setup(self):
        self.conn.execute("INSERT INTO events VALUES ('buyer','delivered','{}','2026-01-02T00:00:00Z')")
        self.assertEqual(self.actions()[0]['action'], 'fulfill_setup')

    def test_recorded_delivery_unlocks_review_only_optional_offer(self):
        self.receipt()
        self.assertTrue(delivery_complete(self.conn, 'buyer', 'pay1'))
        self.assertEqual(self.actions()[0]['action'], 'offer_optional_managed_plan')

    def test_managed_interest_cannot_skip_pending_setup(self):
        self.conn.execute("INSERT INTO events VALUES ('buyer','managed_plan_interested','{}','2026-01-02T00:00:00Z')")
        self.assertEqual(self.actions()[0]['action'], 'fulfill_setup')
        self.receipt()
        self.assertEqual(self.actions()[0]['action'], 'send_managed_checkout')

    def test_opt_out_preserves_internal_obligation_but_blocks_upsell(self):
        self.conn.execute("UPDATE leads SET contact_allowed=0")
        self.conn.execute("INSERT INTO events VALUES ('buyer','opt_out','{}','2026-01-02T00:00:00Z')")
        self.assertEqual(self.actions()[0]['action'], 'fulfill_setup')
        self.receipt()
        self.assertEqual(self.actions(), [])

    def test_refunded_customer_has_no_setup_or_upsell_action(self):
        self.conn.execute("INSERT INTO events VALUES ('buyer','refund','{}','2026-01-02T00:00:00Z')")
        self.assertEqual(self.actions(), [])

    def test_unlinked_or_malformed_sales_fail_closed(self):
        for metadata in ('{}', '[]', 'null', 'broken', '{"processor_event_id":"someone_else"}',
                         '{"processor_event_id":["pay1"]}', '{"processor_event_id":{"id":"pay1"}}'):
            with self.subTest(metadata=metadata):
                self.conn.execute('UPDATE events SET metadata=?', (metadata,))
                self.assertEqual(self.actions()[0]['action'], 'fulfill_setup')

    def test_wrong_customer_and_bad_delivery_evidence_are_rejected(self):
        for change in ({'lead_id': 'other'}, {'event_id': 'missing'},
                       {'artifact_sha256': 'not-a-checksum'}, {'evidence_url': 'http://example.test'},
                       {'evidence_url': 'https://secret@example.test'},
                       {'completed_at': '2025-01-01T00:00:00Z'},
                       {'completed_at': '2999-01-01T00:00:00Z'},
                       {'completed_at': '2026-01-02T00:00:00'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.receipt(**change)

    def test_test_payment_and_nonpositive_amount_rejected(self):
        for processor, amount in [('test', 100), ('sandbox', 100), ('provider', 0), ('provider', -1), ('provider', float('inf'))]:
            self.conn.execute('UPDATE payment_events SET processor=?,amount=?', (processor, amount))
            with self.subTest(processor=processor, amount=amount), self.assertRaises(ValueError):
                self.receipt()

    def test_idempotent_delivery_receipt_cannot_be_replaced(self):
        self.assertFalse(self.receipt()['duplicate'])
        self.assertTrue(self.receipt()['duplicate'])
        with self.assertRaises(ValueError):
            self.receipt(artifact_sha256='b' * 64)

    def test_later_purchase_needs_its_own_delivery(self):
        self.receipt()
        self.conn.execute("INSERT INTO events VALUES ('buyer','sale','{\"processor_event_id\":\"pay2\"}','2026-01-03T00:00:00Z')")
        self.assertEqual(self.actions()[0]['action'], 'fulfill_setup')

    def test_cycle_queues_fulfillment_internally_without_contact_or_owner_review(self):
        self.conn.commit()
        with patch('autonomous_cycle.deliver') as deliver:
            result = autonomous_cycle.run(self.path)
        deliver.assert_not_called()
        self.assertEqual(result['counts']['pending_fulfillment'], 1)
        self.assertEqual(result['owner_review'], [])
        self.assertEqual(result['internal_work'][0]['action'], 'fulfill_setup')

    def test_unknown_or_altered_receipt_does_not_count(self):
        self.assertFalse(delivery_complete(self.conn, 'buyer', 'pay1'))
        self.receipt()
        self.conn.execute("UPDATE setup_delivery_receipts SET artifact_sha256='broken'")
        self.assertFalse(delivery_complete(self.conn, 'buyer', 'pay1'))

    def test_cli_hashes_actual_delivered_file(self):
        self.conn.commit()
        artifact = Path(self.tmp.name) / 'delivery.txt'
        artifact.write_bytes(b'customer delivery content')
        output = subprocess.check_output([
            sys.executable, str(ROOT / 'scripts/setup_fulfillment.py'), 'buyer', 'pay1',
            '--artifact', str(artifact), '--evidence-url', 'https://provider.example.test/delivery/1',
            '--completed-at', '2026-01-02T00:00:00Z'],
            env={**os.environ, 'REVENUE_DB_PATH': self.path}, text=True)
        self.assertTrue(json.loads(output)['recorded'])
        digest = self.conn.execute('SELECT artifact_sha256 FROM setup_delivery_receipts').fetchone()[0]
        self.assertEqual(digest, hashlib.sha256(artifact.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
