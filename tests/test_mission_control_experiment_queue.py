import os
import sqlite3
import tempfile
import unittest

from scripts import mission_control


class MissionControlExperimentQueueTests(unittest.TestCase):
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

    def test_run_creates_one_zero_cost_validation_experiment(self):
        first = mission_control.run(self.path)
        queue = first['zero_cost_validation_queue']
        self.assertEqual(queue['execution_gate'], 'recommendation_only')
        self.assertIsNotNone(queue['experiment'])
        self.assertEqual(queue['experiment']['max_cost'], 0)
        self.assertEqual(queue['experiment']['status'], 'queued')
        self.assertEqual(queue['queue']['queued'], 1)
        actions = [item['action'] for item in first['plan']]
        self.assertIn('prepare_next_zero_cost_validation', actions)

        second = mission_control.run(self.path)
        self.assertTrue(second['zero_cost_validation_queue']['experiment']['duplicate_active'])
        self.assertEqual(second['zero_cost_validation_queue']['queue']['queued'], 1)

    def test_existing_measured_champion_causes_distinct_challenger_to_be_queued(self):
        conn = mission_control.connect(self.path)
        baseline = mission_control.business_model_snapshot(conn)
        champion_seed = baseline['top_candidates'][0]
        mission_control.upsert_business_model_evidence(
            conn,
            champion_seed['id'],
            observed_revenue=1200,
            observed_cost=100,
            conversion_rate=0.30,
            evidence_quality=0.95,
            sample_size=25,
            observed_at=mission_control.now_iso(),
        )
        conn.close()

        result = mission_control.run(self.path)
        competition = result['business_model_intelligence']['portfolio_competition']
        champion = competition.get('champion')
        challenger = competition.get('challenger')
        self.assertIsNotNone(champion)
        self.assertIsNotNone(challenger)
        self.assertEqual(champion['id'], champion_seed['id'])
        self.assertNotEqual(champion['id'], challenger['id'])
        self.assertEqual(result['zero_cost_validation_queue']['candidate_id'], challenger['id'])
        self.assertEqual(result['zero_cost_validation_queue']['experiment']['max_cost'], 0)


if __name__ == '__main__':
    unittest.main()
