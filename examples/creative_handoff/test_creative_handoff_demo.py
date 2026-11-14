import copy
import json
import pathlib
import unittest

from creative_handoff_demo import review, money, https_url

EXAMPLE = json.loads((pathlib.Path(__file__).parent / 'sample_fictional.json').read_text())


class CreativeHandoffTests(unittest.TestCase):
    def test_separate_tracks_and_manual_review(self):
        r = review(EXAMPLE)
        self.assertFalse(r['external_action_allowed'])
        self.assertEqual([x['track'] for x in r['work_items']], ['ad', 'funnel'])
        self.assertIn('creative_human_review_pending', r['work_items'][0]['blockers'])
        self.assertEqual(r['work_items'][1]['status'], 'ready_for_manual_handoff')
        self.assertFalse(r['work_items'][1]['external_action_allowed'])

    def test_cross_client_input_blocked(self):
        d = copy.deepcopy(EXAMPLE)
        d['work_items'][1]['client_id'] = 'OTHER'
        self.assertIn('approved_client_context_not_verified', review(d)['work_items'][1]['blockers'])

    def test_changed_context_version_blocked(self):
        d = copy.deepcopy(EXAMPLE)
        d['work_items'][1]['context_version'] = 'v0'
        self.assertIn('approved_client_context_not_verified', review(d)['work_items'][1]['blockers'])

    def test_duplicate_work_id_blocked(self):
        d = copy.deepcopy(EXAMPLE)
        d['work_items'][1]['id'] = d['work_items'][0]['id']
        self.assertIn('missing_or_duplicate_work_id', review(d)['work_items'][1]['blockers'])

    def test_unknown_cost_blocks(self):
        d = copy.deepcopy(EXAMPLE)
        d['work_items'][1]['tool_costs'][0]['usd'] = 'unknown'
        r = review(d)['work_items'][1]
        self.assertIn('cost_unknown_or_invalid', r['blockers'])
        self.assertIsNone(r['itemized_tool_cost_usd'])

    def test_bad_source_and_price_url(self):
        d = copy.deepcopy(EXAMPLE)
        d['work_items'][1]['source_urls'] = ['http://localhost/private']
        d['work_items'][1]['tool_costs'][0]['pricing_source_url'] = 'https://evil.example/private#token'
        r = review(d)['work_items'][1]
        self.assertIn('source_provenance_missing_or_unsafe', r['blockers'])
        self.assertIn('cost_source_missing', r['blockers'])

    def test_nonfinite_money_rejected(self):
        self.assertIsNone(money('Infinity'))
        self.assertIsNone(money('NaN'))
        self.assertIsNone(money('-1'))
        self.assertIsNone(money('0.001'))
        self.assertIsNone(money(True))

    def test_https_source_validation(self):
        self.assertTrue(https_url('https://example.org/research'))
        self.assertFalse(https_url('https://user:pass@example.org/doc'))
        self.assertFalse(https_url('https://example.org/doc#fragment'))
        self.assertFalse(https_url('https://example.org:8443/doc'))

    def test_deterministic_hash(self):
        self.assertEqual(review(EXAMPLE)['work_items'][0]['artifact_sha256'], review(copy.deepcopy(EXAMPLE))['work_items'][0]['artifact_sha256'])


if __name__ == '__main__':
    unittest.main()
