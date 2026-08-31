import os
import sqlite3
import tempfile
import unittest

from scripts import mission_control


class MissionControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'agent.db')
        conn = sqlite3.connect(self.path)
        conn.execute('CREATE TABLE leads (id TEXT, score INTEGER, contact_allowed INTEGER)')
        conn.execute('CREATE TABLE events (lead_id TEXT, event_type TEXT, value REAL)')
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_to_safe_preparation_mode(self):
        result = mission_control.run(self.path)
        self.assertEqual(result['mode'], 'analysis_and_preparation_only')
        self.assertFalse(result['execution_gate']['external_actions_allowed'])
        self.assertFalse(result['execution_gate']['spending_allowed'])

    def test_verified_revenue_drives_score_and_plan(self):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO leads VALUES ('l1', 80, 1)")
        conn.executemany('INSERT INTO events VALUES (?,?,?)', [
            ('l1', 'sent', 0), ('l1', 'reply', 0), ('l1', 'interested', 0), ('l1', 'sale', 100)])
        conn.commit()
        conn.close()
        result = mission_control.run(self.path)
        self.assertEqual(result['metrics']['verified_net_revenue'], 100)
        self.assertGreater(result['objective_score'], 100)
        self.assertEqual(result['plan'][0]['action'], 'replicate_verified_winning_segment')

    def test_no_leads_prioritizes_approved_source(self):
        result = mission_control.run(self.path)
        self.assertEqual(result['plan'][0]['action'], 'connect_approved_lead_source')

    def test_business_model_intelligence_is_always_primed(self):
        result = mission_control.run(self.path)
        intelligence = result['business_model_intelligence']
        self.assertGreaterEqual(intelligence['catalog_size'], 35)
        self.assertEqual(intelligence['mode'], 'continuous_opportunity_optimization')
        self.assertEqual(intelligence['execution_gate'], 'candidate_only')
        self.assertGreater(len(intelligence['top_candidates']), 0)
        self.assertEqual(result['plan'][-1]['action'], 'validate_top_business_model_candidate')


if __name__ == '__main__':
    unittest.main()
