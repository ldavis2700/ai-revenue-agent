"""Offline pre-sales sample: source isolation and reviewer gates stay fail-closed."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1] / 'examples' / 'creative_handoff'
spec = importlib.util.spec_from_file_location('creative_handoff_demo', HERE / 'creative_handoff_demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
FIXTURE = json.loads((HERE / 'sample_fictional.json').read_text(encoding='utf-8'))


class CreativeHandoffExampleTests(unittest.TestCase):
    def test_review_never_grants_external_action(self):
        result = demo.review(FIXTURE)
        self.assertFalse(result['external_action_allowed'])
        self.assertEqual(result['reviewed_items'], 2)
        self.assertTrue(all(not row['external_action_allowed'] for row in result['work_items']))
        self.assertIn('creative_human_review_pending', result['work_items'][0]['blockers'])
        self.assertEqual(result['work_items'][1]['status'], 'ready_for_manual_handoff')

    def test_cross_client_and_unknown_cost_blocked(self):
        data = copy.deepcopy(FIXTURE)
        data['work_items'][1]['client_id'] = 'different-client'
        data['work_items'][1]['tool_costs'][0]['usd'] = 'unknown'
        issues = demo.review(data)['work_items'][1]['blockers']
        self.assertIn('approved_client_context_not_verified', issues)
        self.assertIn('cost_unknown_or_invalid', issues)

    def test_bad_provenance_and_malformed_track_fail_closed(self):
        data = copy.deepcopy(FIXTURE)
        data['work_items'][1]['track'] = []
        data['work_items'][1]['source_urls'] = ['http://localhost/internal']
        issues = demo.review(data)['work_items'][1]['blockers']
        self.assertIn('unsupported_track', issues)
        self.assertIn('source_provenance_missing_or_unsafe', issues)
        self.assertFalse(demo.https_url('https://example.org:invalid/'))

    def test_fictional_fixture_hash_stable(self):
        before = demo.review(FIXTURE)['work_items'][1]['artifact_sha256']
        after = demo.review(copy.deepcopy(FIXTURE))['work_items'][1]['artifact_sha256']
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
