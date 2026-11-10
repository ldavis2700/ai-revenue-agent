import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from delivery_adapter import deliver
from free_delivery_policy import reserve_request, validate_policy
from free_delivery_fixture import free_policy


class FreeDeliveryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'revenue.db')
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE events (lead_id,event_type,value,metadata,created_at)')
        self.endpoint = 'https://delivery.example.test/send'
        self.policy = free_policy(self.endpoint, limit=1)
        env = patch.dict(os.environ, {
            'DELIVERY_ENABLED': 'true', 'DELIVERY_WEBHOOK_URL': self.endpoint,
            'DELIVERY_WEBHOOK_TOKEN': 'test-secret',
            'DELIVERY_FREE_TIER_POLICY_JSON': json.dumps(self.policy),
            'CONSENTED_INBOUND_DAILY_DELIVERY_CAP': '100',
        })
        env.start()
        self.addCleanup(env.stop)
        self.calls = []

    def action(self, name='one'):
        return {'lead_id': name, 'action': 'send_initial', 'email': name+'@example.test',
                'source': 'owned_inbound_opt_in'}

    def send(self, request):
        self.calls.append(request)
        return SimpleNamespace(status=202)

    def test_no_policy_never_calls_provider_or_leaks_credentials(self):
        with patch.dict(os.environ, {'DELIVERY_FREE_TIER_POLICY_JSON': ''}):
            result = deliver(self.action(), self.path, self.send)
        self.assertEqual(result['reason'], 'free_delivery_policy_required')
        self.assertEqual(self.calls, [])
        self.assertNotIn('test-secret', json.dumps(result))

    def test_paid_unknown_expired_and_mismatched_policies_block_before_network(self):
        now = datetime.now(timezone.utc)
        cases = [
            {'plan': 'paid'}, {'plan': 'trial'}, {'overage_behavior': 'bill'},
            {'request_cost_cents': 1}, {'request_cost_cents': False},
            {'request_cost_cents': '0'}, {'recurring_cost_cents': 100},
            {'upfront_cost_cents': None}, {'request_limit': True},
            {'request_limit': 0}, {'request_limit': float('inf')},
            {'endpoint': 'https://other.example.test/send'},
            {'verified_at': (now+timedelta(hours=1)).isoformat()},
            {'expires_at': (now-timedelta(seconds=1)).isoformat()},
            {'expires_at': (now+timedelta(days=2)).isoformat()},
            {'evidence_url': 'http://example.test/terms'},
            {'evidence_url': 'https://secret@example.test/terms'},
            {'period_start': (now+timedelta(days=1)).isoformat()},
            {'period_end': now.isoformat()}, {'account_id': ''},
        ]
        for change in cases:
            with self.subTest(change=change), patch.dict(os.environ, {
                    'DELIVERY_FREE_TIER_POLICY_JSON': json.dumps({**self.policy, **change})}):
                self.assertEqual(deliver(self.action(), self.path, self.send)['status'], 'blocked')
        self.assertEqual(self.calls, [])

    def test_malformed_policy_fails_closed(self):
        for raw in ('no json', '[]', 'null', 'true', '{}'):
            with self.subTest(raw=raw):
                policy, reason = validate_policy(raw, self.endpoint)
                self.assertIsNone(policy)
                self.assertEqual(reason, 'invalid_free_delivery_policy')

    def test_duplicate_does_not_use_more_quota_and_new_work_stops_at_cap(self):
        self.assertEqual(deliver(self.action(), self.path, self.send)['status'], 'delivered')
        self.assertEqual(deliver(self.action(), self.path, self.send)['status'], 'duplicate')
        self.assertEqual(deliver(self.action('two'), self.path, self.send)['reason'], 'free_delivery_quota_exhausted')
        self.assertEqual(len(self.calls), 1)

    def test_timeout_consumes_quota_across_restarted_connections(self):
        def timeout(request):
            self.calls.append(request)
            raise TimeoutError('provider may have accepted')
        self.assertEqual(deliver(self.action(), self.path, timeout)['status'], 'failed')
        self.assertEqual(deliver(self.action('two'), self.path, self.send)['reason'], 'free_delivery_quota_exhausted')
        self.assertEqual(len(self.calls), 1)

    def test_simultaneous_workers_cannot_exceed_remaining_free_quota(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: deliver(self.action(str(i)), self.path, self.send), range(4)))
        self.assertEqual(sum(r['status']=='delivered' for r in results), 1)
        self.assertEqual(len(self.calls), 1)

    def test_changed_limit_or_overlapping_period_cannot_reset_consumption(self):
        deliver(self.action(), self.path, self.send)
        for change in ({'request_limit': 100}, {'period_start': self.policy['verified_at']}):
            with self.subTest(change=change), patch.dict(os.environ, {
                    'DELIVERY_FREE_TIER_POLICY_JSON': json.dumps({**self.policy, **change})}):
                self.assertEqual(deliver(self.action('two'), self.path, self.send)['reason'], 'free_delivery_quota_conflict')
        self.assertEqual(len(self.calls), 1)

    def test_provider_quota_resets_only_in_a_new_nonoverlapping_period(self):
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.path) as conn:
            self.assertTrue(reserve_request(conn, self.endpoint, now)[0])
        tomorrow = now + timedelta(days=1)
        with patch.dict(os.environ, {'DELIVERY_FREE_TIER_POLICY_JSON': json.dumps(
                free_policy(self.endpoint, limit=1, now=tomorrow))}), sqlite3.connect(self.path) as conn:
            self.assertTrue(reserve_request(conn, self.endpoint, tomorrow)[0])


if __name__ == '__main__':
    unittest.main()
