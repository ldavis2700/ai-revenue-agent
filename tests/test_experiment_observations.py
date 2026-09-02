import os
import tempfile
import unittest

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


if __name__ == '__main__':
    unittest.main()
