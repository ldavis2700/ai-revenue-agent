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
        self.assertGreaterEqual(intelligence['catalog_size'], 100)
        self.assertEqual(intelligence['mode'], 'continuous_opportunity_optimization')
        self.assertEqual(intelligence['execution_gate'], 'candidate_only')
        self.assertGreater(len(intelligence['top_candidates']), 0)
        competition = intelligence['portfolio_competition']
        self.assertEqual(competition['execution_gate'], 'recommendation_only')
        self.assertIn(competition['recommended_action'], {
            'discover_or_repair_candidates', 'validate_challenger', 'continue_measuring_champion',
            'run_bounded_head_to_head_validation', 'protect_winner_and_probe_challenger'})
        actions = [item['action'] for item in result['plan']]
        self.assertIn('evaluate_portfolio_competition', actions)
        self.assertIn('validate_top_business_model_candidate', actions)
        self.assertIn('prepare_next_zero_cost_validation', actions)

    def test_business_model_evidence_persists_across_runs(self):
        conn = mission_control.connect(self.path)
        baseline = mission_control.business_model_snapshot(conn)
        seed = baseline['top_candidates'][0]
        mission_control.upsert_business_model_evidence(
            conn,
            seed['id'],
            observed_revenue=1200,
            observed_cost=100,
            conversion_rate=0.30,
            evidence_quality=0.95,
            sample_size=25,
            observed_at=mission_control.now_iso(),
        )
        conn.close()

        reopened = mission_control.connect(self.path)
        stored = mission_control.load_persisted_evidence(reopened)
        reopened.close()
        self.assertIn(seed['id'], stored)
        self.assertEqual(stored[seed['id']]['observed_revenue'], 1200)
        self.assertEqual(stored[seed['id']]['sample_size'], 25)

        result = mission_control.run(self.path)
        self.assertEqual(result['business_model_intelligence']['evidence_models'], 1)
        candidates = result['business_model_intelligence']['top_candidates']
        self.assertTrue(any(candidate['id'] == seed['id'] for candidate in candidates))
        measured = next(candidate for candidate in candidates if candidate['id'] == seed['id'])
        self.assertIn(measured['experiment_state'], {'continue_validation', 'scale_candidate'})
        competition = result['business_model_intelligence']['portfolio_competition']
        self.assertIsNotNone(competition.get('champion'))
        self.assertIsNotNone(competition.get('challenger'))

    def test_nonfinite_evidence_cannot_insert_or_replace_measurements(self):
        conn = mission_control.connect(self.path)
        self.addCleanup(conn.close)
        mission_control.upsert_business_model_evidence(
            conn, 'existing', observed_revenue=100, observed_cost=10,
            conversion_rate=0.2, evidence_quality=0.8, sample_size=20)
        before = [dict(row) for row in conn.execute('SELECT * FROM business_model_evidence')]
        changes = conn.total_changes
        for model_id in ('existing', 'new'):
            for field in ('observed_revenue', 'observed_cost', 'conversion_rate',
                          'evidence_quality', 'sample_size'):
                for value in (float('nan'), float('inf'), float('-inf'),
                              'NaN', 'Infinity', '-Infinity'):
                    with self.subTest(model_id=model_id, field=field, value=value):
                        with self.assertRaisesRegex(ValueError, field + ' must be finite'):
                            mission_control.upsert_business_model_evidence(
                                conn, model_id, **{field: value})
                        self.assertEqual(conn.total_changes, changes)
                        self.assertEqual([dict(row) for row in conn.execute(
                            'SELECT * FROM business_model_evidence')], before)

    def test_finite_evidence_bounds_and_numeric_strings_remain_compatible(self):
        conn = mission_control.connect(self.path)
        self.addCleanup(conn.close)
        mission_control.upsert_business_model_evidence(
            conn, 'valid', observed_revenue='12.5', observed_cost='-2',
            conversion_rate='2', evidence_quality='-1', sample_size='-4')
        evidence = mission_control.load_persisted_evidence(conn)['valid']
        self.assertEqual(evidence['observed_revenue'], 12.5)
        self.assertEqual(evidence['observed_cost'], 0)
        self.assertEqual(evidence['conversion_rate'], 1)
        self.assertEqual(evidence['evidence_quality'], 0)
        self.assertEqual(evidence['sample_size'], 0)
        mission_control.upsert_business_model_evidence(conn, 'valid', sample_size=None)
        self.assertIsNone(conn.execute(
            'SELECT sample_size FROM business_model_evidence WHERE model_id=?', ('valid',)).fetchone()[0])


if __name__ == '__main__':
    unittest.main()
