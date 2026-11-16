"""Offline regression tests for the opt-in Supabase pilot handoff."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from research_evidence_demo import connect, ingest, review
from supabase_test_handoff import prepared_rows, run, send_test_rows, test_endpoint

class FakeResponse:
    def __init__(self, status=201, body=b''):
        self.status, self.body = status, body
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, limit): return self.body[:limit]

class FakeOpener:
    def __init__(self, rows, *, mismatch=False, fail_readback=False):
        self.requests, self.rows = [], rows
        self.mismatch, self.fail_readback = mismatch, fail_readback
    def open(self, request, timeout):
        self.requests.append(request)
        if request.get_method() == 'POST':
            return FakeResponse()
        if self.fail_readback:
            raise OSError('simulated connection failure')
        returned = dict(self.rows[0])
        if self.mismatch:
            returned['accepted_value'] = 'wrong-value'
        return FakeResponse(200, json.dumps([returned]).encode('utf-8'))

class TestHandoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.tmp.name) / 'demo.sqlite')
        ingest(self.db, [dict(record_id='fiction-a',field_name='lead_time',proposed_value='3',
            source_label='fictional',excerpt='Example: 3 days'),
            dict(record_id='fiction-b',field_name='risk',proposed_value='high',
            source_label='fictional',excerpt='Example: high risk')])
        review(self.db,'fiction-a','correct','Operator','4')
        review(self.db,'fiction-b','reject','Operator')
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_offline_and_approved_only(self):
        with patch('supabase_test_handoff.build_opener',side_effect=AssertionError('network forbidden')):
            result=run(self.db)
        self.assertEqual(result['prepared_approved_rows'],1)
        self.assertEqual(result['remote_requests'],0)
        self.assertEqual(len(result['prepared_approval_keys'][0]),64)
        self.assertEqual(prepared_rows(self.db)[0]['accepted_value'],'4')
    def test_changed_evidence_fails_closed(self):
        with self.db:
            self.db.execute("UPDATE proposals SET excerpt='tampered' WHERE record_id='fiction-a'")
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            run(self.db)
    def test_separate_permission_and_key_required(self):
        rows=prepared_rows(self.db)
        with self.assertRaisesRegex(ValueError,'confirmation'):
            send_test_rows(rows,'https://abcdefghijklmnopqrst.supabase.co','fictional',execute=True)
        with self.assertRaisesRegex(ValueError,'key'):
            send_test_rows(rows,'https://abcdefghijklmnopqrst.supabase.co',None,
                           execute=True,confirmed=True)
    def test_disallow_bad_endpoints(self):
        for url in ('http://abcdefghijklmnopqrst.supabase.co',
            'https://abcdefghijklmnopqrst.supabase.co.evil.org',
            'https://abcdefghijklmnopqrst.supabase.co/rest/v1/users',
            'https://apikey@abcdefghijklmnopqrst.supabase.co',
            'https://localhost:8000'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                test_endpoint(url)
    def test_mocked_explicit_test_request(self):
        rows = prepared_rows(self.db)
        fake = FakeOpener(rows)
        with patch('supabase_test_handoff.build_opener', return_value=fake):
            result = send_test_rows(rows,
                'https://abcdefghijklmnopqrst.supabase.co', 'fictional',
                execute=True, confirmed=True)
        self.assertEqual(result['remote_requests'], 2)
        self.assertEqual(result['submitted_rows'], 1)
        self.assertEqual(result['verified_persisted_rows'], 1)
        self.assertEqual(len(fake.requests), 2)
        self.assertEqual(fake.requests[0].get_method(), 'POST')
        self.assertEqual(fake.requests[1].get_method(), 'GET')
        self.assertIn('approval_key=eq.', fake.requests[1].full_url)

    def test_mismatched_readback_does_not_claim_success(self):
        rows = prepared_rows(self.db)
        fake = FakeOpener(rows, mismatch=True)
        with patch('supabase_test_handoff.build_opener', return_value=fake):
            with self.assertRaisesRegex(ValueError, 'may have committed'):
                send_test_rows(rows, 'https://abcdefghijklmnopqrst.supabase.co',
                    'fictional', execute=True, confirmed=True)
        self.assertEqual(len(fake.requests), 2)

    def test_unavailable_readback_has_uncertain_outcome(self):
        rows = prepared_rows(self.db)
        fake = FakeOpener(rows, fail_readback=True)
        with patch('supabase_test_handoff.build_opener', return_value=fake):
            with self.assertRaisesRegex(ValueError, 'reconcile approval keys'):
                send_test_rows(rows, 'https://abcdefghijklmnopqrst.supabase.co',
                    'fictional', execute=True, confirmed=True)
        self.assertEqual(len(fake.requests), 2)

    def test_batch_guard_rejects_before_post(self):
        rows = prepared_rows(self.db)
        with patch('supabase_test_handoff.build_opener',
                   side_effect=AssertionError('network forbidden')):
            with self.assertRaisesRegex(ValueError, 'oversized'):
                send_test_rows(rows * 21,
                    'https://abcdefghijklmnopqrst.supabase.co', 'fictional',
                    execute=True, confirmed=True)
            bad = [dict(rows[0], approval_key='invalid')]
            with self.assertRaisesRegex(ValueError, 'Invalid'):
                send_test_rows(bad,
                    'https://abcdefghijklmnopqrst.supabase.co', 'fictional',
                    execute=True, confirmed=True)

if __name__ == '__main__':
    unittest.main()
