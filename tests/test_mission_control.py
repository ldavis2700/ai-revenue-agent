import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

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

    def test_unverified_sale_claim_does_not_drive_score_or_plan(self):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO leads VALUES ('l1', 80, 1)")
        conn.executemany('INSERT INTO events VALUES (?,?,?)', [
            ('l1', 'sent', 0), ('l1', 'reply', 0),
            ('l1', 'interested', 0), ('l1', 'sale', 100)])
        conn.commit()
        conn.close()
        result = mission_control.run(self.path)
        metrics = result['metrics']
        self.assertEqual(metrics['claimed_sale_events'], 1)
        self.assertEqual(metrics['claimed_sale_value'], 100)
        self.assertEqual(
            metrics['claimed_sale_status'],
            'unverified_not_collected_revenue')
        self.assertEqual(metrics['verified_collected_payments'], 0)
        self.assertEqual(metrics['verified_net_revenue'], 0)
        self.assertEqual(result['objective_score'], 25)
        self.assertNotEqual(
            result['plan'][0]['action'], 'replicate_verified_winning_segment')

    def test_settled_opportunity_payments_feed_mission_metrics_without_double_refunds(self):
        conn = sqlite3.connect(self.path)
        conn.execute('''CREATE TABLE payment_receipts (
            receipt_id TEXT PRIMARY KEY,
            gross_amount_cents INTEGER NOT NULL,
            fee_amount_cents INTEGER NOT NULL,
            net_amount_cents INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE recurring_payment_receipts (
            receipt_id TEXT PRIMARY KEY,
            gross_amount_cents INTEGER NOT NULL,
            fee_amount_cents INTEGER NOT NULL,
            net_amount_cents INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE recurring_payout_availability_receipts (
            receipt_id TEXT PRIMARY KEY,
            amount_cents INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE recurring_bank_receipts (
            receipt_id TEXT PRIMARY KEY,
            amount_cents INTEGER NOT NULL
        )''')
        conn.executemany('INSERT INTO events VALUES (?,?,?)', [
            ('l1', 'sent', 0), ('l1', 'sale', 100), ('l1', 'refund', 20)])
        conn.execute(
            "INSERT INTO payment_receipts VALUES ('payr_1',50000,2500,47500)")
        conn.execute(
            "INSERT INTO recurring_payment_receipts "
            "VALUES ('recurpay_1',15000,500,14500)")
        conn.execute(
            "INSERT INTO recurring_payout_availability_receipts "
            "VALUES ('recuravail_1',14500)")
        conn.execute(
            "INSERT INTO recurring_bank_receipts "
            "VALUES ('recurbank_1',14500)")
        conn.commit()
        metrics = mission_control.snapshot(conn)
        conn.close()
        self.assertEqual(metrics['sales'], 2)
        self.assertEqual(metrics['claimed_sale_events'], 1)
        self.assertEqual(metrics['claimed_sale_value'], 100)
        self.assertEqual(metrics['claimed_refund_value'], 20)
        self.assertEqual(metrics['verified_collected_payments'], 2)
        self.assertEqual(metrics['verified_one_time_payment_receipts'], 1)
        self.assertEqual(metrics['verified_recurring_payment_receipts'], 1)
        self.assertEqual(metrics['verified_recurring_gross_revenue'], 150)
        self.assertEqual(metrics['verified_recurring_fees'], 5)
        self.assertEqual(metrics['verified_recurring_net_revenue'], 145)
        self.assertEqual(
            metrics['verified_recurring_withdrawable_balance'], 145)
        self.assertEqual(metrics['verified_recurring_money_received'], 145)
        self.assertEqual(metrics['verified_opportunity_gross_revenue'], 650)
        self.assertEqual(metrics['verified_opportunity_fees'], 30)
        self.assertEqual(metrics['verified_opportunity_net_revenue'], 620)
        self.assertEqual(metrics['verified_gross_revenue'], 650)
        self.assertEqual(metrics['verified_net_revenue'], 620)
        self.assertEqual(mission_control.objective_score(metrics), 720)

    def test_missing_payment_table_remains_backward_compatible(self):
        conn = sqlite3.connect(self.path)
        metrics = mission_control.snapshot(conn)
        conn.close()
        self.assertEqual(metrics['verified_collected_payments'], 0)
        self.assertEqual(metrics['verified_recurring_payment_receipts'], 0)
        self.assertEqual(metrics['verified_recurring_net_revenue'], 0)
        self.assertEqual(metrics['verified_recurring_withdrawable_balance'], 0)
        self.assertEqual(metrics['verified_recurring_money_received'], 0)
        self.assertEqual(metrics['verified_opportunity_net_revenue'], 0)

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
        self.assertEqual(measured['experiment_state'], 'validate')
        self.assertFalse(measured['economics_verified'])
        self.assertEqual(measured['observed_profit'], 0)
        self.assertEqual(measured['claimed_observed_revenue'], 1200)
        competition = result['business_model_intelligence']['portfolio_competition']
        self.assertIsNone(competition.get('champion'))
        self.assertIsNotNone(competition.get('challenger'))

    def test_recurring_growth_and_cross_opportunity_reuse_feed_model_evidence(self):
        conn = mission_control.connect(self.path)
        conn.execute('''CREATE TABLE opportunities (
            id TEXT PRIMARY KEY, payload_json TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE recurring_payment_receipts (
            receipt_id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
            net_amount_cents INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE recurring_realized_unit_economics (
            economics_id TEXT PRIMARY KEY, opportunity_id TEXT,
            recurring_payment_receipt_id TEXT NOT NULL,
            contribution_cents INTEGER NOT NULL,
            delivery_cost_cents INTEGER NOT NULL,
            inference_cost_cents INTEGER NOT NULL,
            cac_cents INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE realized_unit_economics (
            economics_id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
            contribution_cents INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE recurring_growth_evidence_receipts (
            receipt_id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
            recurring_payment_receipt_id TEXT NOT NULL,
            recurring_economics_id TEXT NOT NULL, kind TEXT NOT NULL,
            prior_recurring_payment_receipt_id TEXT,
            baseline_value_cents INTEGER, expanded_value_cents INTEGER,
            occurred_at TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE reusable_ip_assets (
            asset_id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
            name TEXT NOT NULL, asset_type TEXT NOT NULL,
            maturity TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE reusable_ip_reuse_receipts (
            receipt_id TEXT PRIMARY KEY,
            source_asset_id TEXT NOT NULL,
            source_opportunity_id TEXT NOT NULL,
            reused_asset_id TEXT NOT NULL,
            reused_opportunity_id TEXT NOT NULL,
            economics_kind TEXT NOT NULL,
            economics_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        )''')
        payload = json.dumps({
            'offer_family': 'multi_system_operational_integration'})
        conn.executemany(
            "INSERT INTO opportunities VALUES (?,?)", [
                ('opp_1', payload), ('opp_2', '{}'), ('opp_3', '{}')])
        conn.execute(
            "INSERT INTO recurring_payment_receipts VALUES (?,?,?)",
            ('recur_2', 'opp_1', 14500))
        conn.execute(
            "INSERT INTO recurring_realized_unit_economics "
            "VALUES (?,?,?,?,?,?,?)",
            ('econ_2', 'opp_1', 'recur_2', 12000, 1500, 500, 500))
        conn.executemany(
            "INSERT INTO recurring_growth_evidence_receipts "
            "VALUES (?,?,?,?,?,?,?,?,?)", [
                ('grow_ret', 'opp_1', 'recur_2', 'econ_2', 'retention',
                 'recur_1', None, None, '2026-09-26T23:00:00+00:00'),
                ('grow_exp', 'opp_1', 'recur_2', 'econ_2', 'expansion',
                 None, 50000, 75000, '2026-09-26T23:05:00+00:00'),
            ])
        conn.executemany(
            "INSERT INTO reusable_ip_assets VALUES (?,?,?,?,?)", [
                ('asset_1', 'opp_1', 'Managed integration workflow',
                 'workflow', 'productize_candidate'),
                ('asset_2', 'opp_2', 'managed integration workflow',
                 'workflow', 'learned'),
                ('asset_3', 'opp_3', 'Different workflow',
                 'workflow', 'learned'),
            ])
        conn.executemany(
            "INSERT INTO realized_unit_economics VALUES (?,?,?)", [
                ('econ_reuse', 'opp_2', 9000),
                ('econ_invalid', 'opp_3', -1),
            ])
        conn.executemany(
            "INSERT INTO reusable_ip_reuse_receipts VALUES (?,?,?,?,?,?,?,?)", [
                ('reuse_valid', 'asset_1', 'opp_1', 'asset_2', 'opp_2',
                 'one_time', 'econ_reuse', '2026-09-26T23:10:00+00:00'),
                ('reuse_invalid', 'asset_1', 'opp_1', 'asset_3', 'opp_3',
                 'one_time', 'econ_invalid', '2026-09-26T23:11:00+00:00'),
            ])
        conn.commit()

        with patch.object(
                mission_control, '_verified_recurring_growth_evidence'), \
             patch.object(
                mission_control, '_verified_reusable_ip_reuse_evidence'), \
             patch.object(
                mission_control, '_verified_reusable_ip_maturity',
                return_value={'maturity': 'productize_candidate'}):
            evidence = mission_control.ledger_business_model_evidence(conn)
            snapshot = mission_control.business_model_snapshot(conn)
        conn.close()

        model = evidence['ai_agent_implementation']
        self.assertTrue(model['_ledger_verified'])
        self.assertEqual(model['verified_retention_receipts'], 1)
        self.assertEqual(model['verified_expansion_receipts'], 1)
        self.assertEqual(model['verified_reuse_receipts'], 1)
        self.assertEqual(model['verified_reused_opportunities'], 1)
        self.assertEqual(model['realized_recurring_net_cents'], 14500)
        self.assertEqual(
            model['realized_recurring_contribution_cents'], 12000)
        self.assertEqual(model['retained_recurring_value_cents'], 14500)
        self.assertEqual(model['expanded_value_delta_cents'], 25000)
        self.assertEqual(model['mastery'], 'productize_candidate')
        self.assertEqual(len(model['receipt_lineage']), 2)
        self.assertEqual(len(model['reuse_receipt_lineage']), 1)
        self.assertEqual(
            model['reuse_receipt_lineage'][0]['reuse_receipt_id'],
            'reuse_valid')
        self.assertEqual(snapshot['ledger_verified_evidence_models'], 1)
        verified = snapshot['verified_model_evidence'][
            'ai_agent_implementation']
        self.assertEqual(verified['observed_revenue'], 145)
        self.assertEqual(verified['verified_reuse_receipts'], 1)

    def test_verified_one_time_forecasts_feed_model_calibration(self):
        conn = mission_control.connect(self.path)
        conn.execute('''CREATE TABLE opportunities (
            id TEXT PRIMARY KEY, payload_json TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE payment_receipts (
            receipt_id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
            net_amount_cents INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE realized_unit_economics (
            economics_id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
            payment_receipt_id TEXT NOT NULL,
            delivery_cost_cents INTEGER NOT NULL,
            inference_cost_cents INTEGER NOT NULL,
            cac_cents INTEGER NOT NULL,
            measured_at TEXT NOT NULL, evidence_json TEXT NOT NULL
        )''')
        conn.execute(
            "INSERT INTO opportunities VALUES (?,?)",
            ('opp_1', json.dumps({
                'offer_family': 'multi_system_operational_integration'})))
        conn.execute(
            "INSERT INTO payment_receipts VALUES (?,?,?)",
            ('pay_1', 'opp_1', 70000))
        conn.execute(
            "INSERT INTO realized_unit_economics VALUES (?,?,?,?,?,?,?,?)",
            ('econ_1', 'opp_1', 'pay_1', 20000, 2000, 5000,
             '2026-09-27T00:00:00+00:00', json.dumps({
                 'proposal_projection_comparison': {
                     'projected_contribution_cents': 73000,
                     'contribution_variance_cents': -3000,
                 }})))
        conn.commit()
        with patch.object(
                mission_control, '_verified_realized_economics') as verify:
            evidence = mission_control.ledger_business_model_evidence(conn)
        conn.close()
        verify.assert_called_once_with(conn, 'econ_1')
        model = evidence['ai_agent_implementation']
        self.assertEqual(model['verified_forecast_comparisons'], 1)
        self.assertEqual(model['forecast_mean_absolute_error_cents'], 3000)
        self.assertEqual(
            model['forecast_mean_projected_contribution_cents'], 73000)
        self.assertEqual(model['observed_revenue'], 700)
        self.assertEqual(model['observed_cost'], 270)
        self.assertTrue(model['_ledger_verified'])

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
