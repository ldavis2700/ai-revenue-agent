import json
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import autonomous_cycle
import delivery_adapter
from dispatch_recovery import dispatch_actions
from free_delivery_fixture import free_policy


class DispatchRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'revenue.db')
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE events (lead_id,event_type,value,metadata,created_at)')
        self.env = patch.dict(os.environ, {
            'DELIVERY_ENABLED': 'true',
            'DELIVERY_WEBHOOK_URL': 'https://example.test/authorized-delivery',
            'DELIVERY_WEBHOOK_TOKEN': 'test-only-secret',
            'CONSENTED_INBOUND_AUTOMATION_ENABLED': 'true',
            'REVENUE_AGENT_KILL_SWITCH': 'false',
            'CONSENTED_INBOUND_DAILY_DELIVERY_CAP': '20',
            'DELIVERY_FREE_TIER_POLICY_JSON': json.dumps(free_policy('https://example.test/authorized-delivery')),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.actions = [self.action('one'), self.action('two')]
        self.calls = []

    def action(self, lead_id):
        return {'lead_id': lead_id, 'action': 'send_initial',
                'email': lead_id + '@example.test', 'source': 'owned_inbound_opt_in'}

    def success(self, action, path):
        def transport(request):
            self.calls.append(action['lead_id'])
            return SimpleNamespace(status=200)
        return delivery_adapter.deliver(action, path, transport=transport)

    def pending(self):
        with sqlite3.connect(self.path) as conn:
            return conn.execute('SELECT COUNT(*) FROM autonomous_dispatch_pending').fetchone()[0]

    def test_fault_does_not_starve_independent_action(self):
        def transport(action, path):
            if action['lead_id'] == 'one':
                raise RuntimeError('private-token-and-email-must-not-appear')
            return self.success(action, path)
        result = dispatch_actions(self.actions, self.path, transport)
        self.assertEqual([x['status'] for x in result], ['uncertain', 'delivered'])
        self.assertEqual(self.calls, ['two'])
        self.assertEqual(self.pending(), 1)
        self.assertNotIn('private-token', json.dumps(result))

    def test_uncertain_action_is_not_replayed_on_next_cycle(self):
        def fail(*args):
            raise RuntimeError('unknown delivery outcome')
        dispatch_actions(self.actions[:1], self.path, fail)
        result = dispatch_actions(self.actions, self.path, self.success)
        self.assertEqual([x['status'] for x in result], ['uncertain', 'delivered'])
        self.assertEqual(self.calls, ['two'])

    def test_changed_payload_cannot_bypass_uncertain_work(self):
        dispatch_actions(self.actions[:1], self.path, lambda *a: {'status': 'failed'})
        changed = {**self.actions[0], 'email': 'changed@example.test'}
        result = dispatch_actions([changed], self.path, self.success)
        self.assertEqual(result[0]['status'], 'uncertain')
        self.assertEqual(self.calls, [])

    def test_provider_timeout_does_not_retry_even_after_recovery(self):
        def timeout(action, path):
            def transport(request):
                self.calls.append('provider-may-have-accepted')
                raise TimeoutError()
            return delivery_adapter.deliver(action, path, transport=transport)
        self.assertEqual(dispatch_actions(self.actions[:1], self.path, timeout)[0]['status'], 'uncertain')
        self.assertEqual(dispatch_actions(self.actions[:1], self.path, self.success)[0]['status'], 'uncertain')
        self.assertEqual(self.calls, ['provider-may-have-accepted'])

    def test_restart_after_receipt_commit_recovers_without_resend(self):
        def interrupted(action, path):
            self.success(action, path)
            raise SystemExit()
        with self.assertRaises(SystemExit):
            dispatch_actions(self.actions[:1], self.path, interrupted)
        self.assertEqual(self.pending(), 1)
        result = dispatch_actions(self.actions[:1], self.path, self.success)
        self.assertEqual(result[0]['reason'], 'committed_receipt_recovered')
        self.assertEqual(self.calls, ['one'])
        self.assertEqual(self.pending(), 0)

    def test_interrupt_before_receipt_stays_quarantined(self):
        def interrupted(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            dispatch_actions(self.actions[:1], self.path, interrupted)
        self.assertEqual(dispatch_actions(self.actions[:1], self.path, self.success)[0]['status'], 'uncertain')
        self.assertEqual(self.calls, [])

    def test_normal_disabled_delivery_can_resume_later(self):
        with patch.dict(os.environ, {'DELIVERY_ENABLED': 'false'}):
            self.assertEqual(dispatch_actions(self.actions[:1], self.path, self.success)[0]['status'], 'blocked')
        self.assertEqual(self.pending(), 0)
        self.assertEqual(dispatch_actions(self.actions[:1], self.path, self.success)[0]['status'], 'delivered')

    def test_claimed_success_without_receipt_is_not_trusted(self):
        result = dispatch_actions(self.actions[:1], self.path, lambda *a: {'status': 'delivered'})
        self.assertEqual(result[0]['reason'], 'delivery_receipt_not_committed')
        self.assertEqual(self.pending(), 1)

    def test_malformed_result_is_isolated(self):
        for bad in (None, {}, {'status': 'invented'}):
            with self.subTest(result=bad):
                action = self.action(str(bad))
                result = dispatch_actions([action], self.path, lambda *a: bad)
                self.assertEqual(result[0]['reason'], 'invalid_delivery_result')

    def test_stop_control_is_respected_between_actions(self):
        def deliver_then_stop(action, path):
            result = self.success(action, path)
            os.environ['REVENUE_AGENT_KILL_SWITCH'] = 'true'
            return result
        result = dispatch_actions(self.actions, self.path, deliver_then_stop)
        self.assertEqual([x['status'] for x in result], ['delivered', 'blocked'])
        self.assertEqual(self.calls, ['one'])

    def test_journal_failure_prevents_external_delivery(self):
        result = dispatch_actions(self.actions, self.tmp.name, self.success)
        self.assertEqual([x['status'] for x in result], ['uncertain', 'uncertain'])
        self.assertEqual(self.calls, [])

    def test_concurrent_cycle_cannot_claim_same_work(self):
        entered, release = threading.Event(), threading.Event()
        def slow(action, path):
            entered.set()
            if not release.wait(5):
                raise TimeoutError()
            return self.success(action, path)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(dispatch_actions, self.actions[:1], self.path, slow)
            self.assertTrue(entered.wait(5))
            try:
                second = dispatch_actions(self.actions[:1], self.path, self.success)
                self.assertEqual(second[0]['status'], 'uncertain')
            finally:
                release.set()
            self.assertEqual(future.result()[0]['status'], 'delivered')
        self.assertEqual(self.calls, ['one'])

    def test_run_preserves_internal_work_and_reports_faults(self):
        internal = {'lead_id': 'paid', 'action': 'fulfill_setup'}
        actions = self.actions + [internal]
        def deliver(action, path):
            if action['lead_id'] == 'one':
                raise ValueError('bad task')
            return self.success(action, path)
        with patch.object(autonomous_cycle, 'load_actions', return_value=actions), \
             patch.object(autonomous_cycle, 'lead_sources', return_value={
                 'one': 'owned_inbound_opt_in', 'two': 'owned_inbound_opt_in'}), \
             patch.object(autonomous_cycle, 'deliver', side_effect=deliver):
            result = autonomous_cycle.run(self.path)
        self.assertEqual(result['internal_work'], [internal])
        self.assertEqual(result['counts']['delivered'], 1)
        self.assertEqual(result['counts']['reconciliation_required'], 1)
        self.assertEqual(result['cycle_status'], 'needs_reconciliation')


if __name__ == '__main__':
    unittest.main()
