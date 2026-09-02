import os
import tempfile
import unittest
from unittest.mock import patch

from scripts import experiment_observations


class ExperimentObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'agent.db')
        self.conn = experiment_observations.connect(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_history_is_append_only(self):
        first = experiment_observations.append_observation(
            self.conn, 'directory', experiment_id=1, observed_revenue=100,
            observed_cost=10, conversion_rate=0.10, evidence_quality=0.8,
            sample_size=10, observed_at='2026-08-30T00:00:00+00:00')
        second = experiment_observations.append_observation(
            self.conn, 'directory', experiment_id=2, observed_revenue=200,
            observed_cost=20, conversion_rate=0.20, evidence_quality=0.9,
            sample_size=20, observed_at='2026-08-31T00:00:00+00:00')
        history = experiment_observations.observation_history(self.conn, 'directory')
        self.assertEqual(len(history), 2)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(history[0]['experiment_id'], 2)

    def test_aggregate_preserves_total_economics_and_weights_rates_by_samples(self):
        experiment_observations.append_observation(
            self.conn, 'directory', observed_revenue=100, observed_cost=10,
            conversion_rate=0.10, evidence_quality=0.8, sample_size=10,
            observed_at='2026-08-30T00:00:00+00:00')
        experiment_observations.append_observation(
            self.conn, 'directory', observed_revenue=200, observed_cost=20,
            conversion_rate=0.20, evidence_quality=0.9, sample_size=20,
            observed_at='2026-08-31T00:00:00+00:00')
        aggregate = experiment_observations.aggregate_observations(self.conn, 'directory')
        self.assertEqual(aggregate['observation_count'], 2)
        self.assertEqual(aggregate['observed_revenue'], 300)
        self.assertEqual(aggregate['observed_cost'], 30)
        self.assertEqual(aggregate['sample_size'], 30)
        self.assertAlmostEqual(aggregate['conversion_rate'], 1/6, places=6)
        self.assertAlmostEqual(aggregate['evidence_quality'], 0.866667, places=6)
        self.assertEqual(aggregate['observed_at'], '2026-08-31T00:00:00+00:00')

    def test_bounds_untrusted_measurements(self):
        row = experiment_observations.append_observation(
            self.conn, 'micro_saas', observed_revenue=-5, observed_cost=-2,
            conversion_rate=3, evidence_quality=-1, sample_size=-4)
        self.assertEqual(row['observed_revenue'], 0)
        self.assertEqual(row['observed_cost'], 0)
        self.assertEqual(row['conversion_rate'], 1)
        self.assertEqual(row['evidence_quality'], 0)
        self.assertEqual(row['sample_size'], 0)

    def test_nonfinite_inputs_cannot_change_history_or_aggregate(self):
        experiment_observations.append_observation(
            self.conn, 'directory', observed_revenue=100, observed_cost=10,
            conversion_rate=0.1, evidence_quality=0.8, sample_size=10)
        history = experiment_observations.observation_history(self.conn, 'directory')
        aggregate = experiment_observations.aggregate_observations(self.conn, 'directory')
        for field in ('observed_revenue', 'observed_cost', 'conversion_rate',
                      'evidence_quality', 'sample_size'):
            for invalid in (float('nan'), float('inf'), float('-inf'),
                            'NaN', 'Infinity', '-Infinity'):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, field + ' must be finite'):
                        experiment_observations.append_observation(
                            self.conn, 'directory', **{field: invalid})
                    self.assertEqual(experiment_observations.observation_history(
                        self.conn, 'directory'), history)
                    self.assertEqual(experiment_observations.aggregate_observations(
                        self.conn, 'directory'), aggregate)

    def test_finite_numeric_strings_and_unknown_sample_size_remain_supported(self):
        row = experiment_observations.append_observation(
            self.conn, 'directory', observed_revenue='12.5', observed_cost='2',
            conversion_rate='0.25', evidence_quality='0.8', sample_size=None)
        self.assertEqual(row['observed_revenue'], 12.5)
        self.assertEqual(row['observed_cost'], 2)
        self.assertEqual(row['conversion_rate'], 0.25)
        self.assertEqual(row['evidence_quality'], 0.8)
        self.assertIsNone(row['sample_size'])

    def test_invalid_timestamps_do_not_change_the_ledger(self):
        fixed_now = '2026-09-02T10:00:00+00:00'
        with patch.object(experiment_observations, 'now_iso', return_value=fixed_now):
            experiment_observations.append_observation(self.conn, 'directory', observed_revenue=100)
            before = experiment_observations.observation_history(self.conn, 'directory')
            aggregate = experiment_observations.aggregate_observations(self.conn, 'directory')
            changes = self.conn.total_changes
            for invalid in ('', 'garbage', '2026-02-30T00:00:00+00:00',
                            '2026-09-02', '2026-09-02T09:00:00',
                            '2026-09-02T10:00:00.000001+00:00',
                            '2026-09-02T12:00:00+01:00',
                            0, False, [], {}, float('nan')):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ValueError, 'observed_at'):
                        experiment_observations.append_observation(
                            self.conn, 'directory', observed_revenue=999,
                            observed_at=invalid)
                    self.assertEqual(self.conn.total_changes, changes)
                    self.assertEqual(experiment_observations.observation_history(
                        self.conn, 'directory'), before)
                    self.assertEqual(experiment_observations.aggregate_observations(
                        self.conn, 'directory'), aggregate)

    def test_offsets_are_normalized_before_chronological_ordering(self):
        with patch.object(experiment_observations, 'now_iso',
                          return_value='2026-09-02T10:00:00+00:00'):
            older = experiment_observations.append_observation(
                self.conn, 'directory', observed_at='2026-09-02T09:30:00+02:00')
            newer = experiment_observations.append_observation(
                self.conn, 'directory', observed_at='2026-09-02T08:00:00Z')
            self.assertEqual(older['observed_at'], '2026-09-02T07:30:00+00:00')
            self.assertEqual(newer['observed_at'], '2026-09-02T08:00:00+00:00')
            history = experiment_observations.observation_history(self.conn, 'directory')
            self.assertEqual([row['id'] for row in history], [newer['id'], older['id']])
            self.assertEqual(experiment_observations.aggregate_observations(
                self.conn, 'directory')['observed_at'], newer['observed_at'])

    def test_omitted_timestamp_and_exact_now_remain_valid(self):
        fixed_now = '2026-09-02T10:00:00+00:00'
        with patch.object(experiment_observations, 'now_iso', return_value=fixed_now):
            for observed_at in (None, fixed_now, '2026-09-02T12:00:00+02:00'):
                row = experiment_observations.append_observation(
                    self.conn, 'directory', observed_at=observed_at)
                self.assertEqual(row['observed_at'], fixed_now)
                self.assertEqual(row['created_at'], fixed_now)


if __name__ == '__main__':
    unittest.main()
