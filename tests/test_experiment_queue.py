import os
import tempfile
import unittest

from scripts import experiment_queue


class ExperimentQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'agent.db')
        self.conn = experiment_queue.connect(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_queue_is_recommendation_only_and_deduplicates_active_model(self):
        first = experiment_queue.enqueue_experiment(
            self.conn, 'directory', 'Paid listings convert', 'conversion_rate', 0.10,
            priority=10, max_cost=50, max_samples=20)
        duplicate = experiment_queue.enqueue_experiment(
            self.conn, 'directory', 'Another hypothesis', 'conversion_rate', 0.20)
        self.assertFalse(first['duplicate_active'])
        self.assertTrue(duplicate['duplicate_active'])
        self.assertEqual(first['execution_gate'], 'recommendation_only')

    def test_priority_selects_next_experiment(self):
        experiment_queue.enqueue_experiment(
            self.conn, 'templates', 'Templates convert', 'conversion_rate', 0.05, priority=50)
        experiment_queue.enqueue_experiment(
            self.conn, 'directory', 'Directory converts', 'conversion_rate', 0.05, priority=5)
        nxt = experiment_queue.next_experiment(self.conn)
        self.assertEqual(nxt['model_id'], 'directory')

    def test_target_achievement_completes_experiment(self):
        queued = experiment_queue.enqueue_experiment(
            self.conn, 'directory', 'Directory converts', 'conversion_rate', 0.10,
            max_cost=100, max_samples=20)
        experiment_queue.start_experiment(self.conn, queued['id'])
        result = experiment_queue.record_measurement(
            self.conn, queued['id'], observed_value=0.12, observed_cost=20, sample_size=10)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['outcome'], 'target_achieved')

    def test_cost_cap_stops_experiment_before_scaling(self):
        queued = experiment_queue.enqueue_experiment(
            self.conn, 'micro_saas', 'Trial converts', 'conversion_rate', 0.20,
            max_cost=25, max_samples=50)
        experiment_queue.start_experiment(self.conn, queued['id'])
        result = experiment_queue.record_measurement(
            self.conn, queued['id'], observed_value=0.05, observed_cost=30, sample_size=8)
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(result['outcome'], 'cost_cap_exceeded')

    def test_zero_cost_cap_means_zero_spend(self):
        queued = experiment_queue.enqueue_experiment(
            self.conn, 'directory', 'Organic validation works', 'conversion_rate', 0.10,
            max_cost=0, max_samples=20)
        experiment_queue.start_experiment(self.conn, queued['id'])
        result = experiment_queue.record_measurement(
            self.conn, queued['id'], observed_value=0.02, observed_cost=0.01, sample_size=2)
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(result['outcome'], 'cost_cap_exceeded')

    def test_sample_cap_finishes_without_false_win(self):
        queued = experiment_queue.enqueue_experiment(
            self.conn, 'paid_api', 'API converts', 'conversion_rate', 0.25,
            max_cost=100, max_samples=10)
        experiment_queue.start_experiment(self.conn, queued['id'])
        result = experiment_queue.record_measurement(
            self.conn, queued['id'], observed_value=0.08, observed_cost=10, sample_size=10)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['outcome'], 'sample_cap_reached_without_target')

    def test_nonfinite_limits_are_rejected_without_inserting_experiments(self):
        for field in ('target_value', 'max_cost', 'max_samples'):
            for value in (float('nan'), float('inf'), float('-inf'), 'NaN', 'Infinity', '-Infinity'):
                with self.subTest(field=field, value=value):
                    limits = dict(target_value=0.1, max_cost=0, max_samples=20)
                    limits[field] = value
                    with self.assertRaisesRegex(ValueError, field + ' must be finite'):
                        experiment_queue.enqueue_experiment(
                            self.conn, 'invalid-limits', 'Bounded test', 'conversion_rate', **limits)
                    count = self.conn.execute('SELECT COUNT(*) FROM business_model_experiments').fetchone()[0]
                    self.assertEqual(count, 0)

    def test_nonfinite_measurements_preserve_previous_state(self):
        queued = experiment_queue.enqueue_experiment(
            self.conn, 'directory', 'Measured demand', 'conversion_rate', 0.10,
            max_cost=0, max_samples=20)
        experiment_queue.start_experiment(self.conn, queued['id'])
        experiment_queue.record_measurement(
            self.conn, queued['id'], observed_value=0.02, observed_cost=0, sample_size=2)
        before = dict(self.conn.execute(
            'SELECT * FROM business_model_experiments WHERE id=?', (queued['id'],)).fetchone())
        for field in ('observed_value', 'observed_cost', 'sample_size'):
            for value in (float('nan'), float('inf'), float('-inf'), 'NaN', 'Infinity', '-Infinity'):
                with self.subTest(field=field, value=value):
                    measurement = dict(observed_value=0.03, observed_cost=0, sample_size=3)
                    measurement[field] = value
                    with self.assertRaisesRegex(ValueError, field + ' must be finite'):
                        experiment_queue.record_measurement(self.conn, queued['id'], **measurement)
                    after = dict(self.conn.execute(
                        'SELECT * FROM business_model_experiments WHERE id=?', (queued['id'],)).fetchone())
                    self.assertEqual(after, before)

    def test_finite_numeric_strings_and_existing_negative_bounds_are_preserved(self):
        queued = experiment_queue.enqueue_experiment(
            self.conn, 'directory', 'Measured demand', 'conversion_rate', '0.10',
            max_cost='-1', max_samples='20')
        self.assertEqual(queued['max_cost'], 0)
        result = experiment_queue.record_measurement(
            self.conn, queued['id'], observed_value='0.02', observed_cost='-2', sample_size='-3')
        self.assertEqual(result['status'], 'running')
        self.assertEqual(result['observed_cost'], 0)
        self.assertEqual(result['sample_size'], 0)
        self.assertEqual(result['execution_gate'], 'recommendation_only')


if __name__ == '__main__':
    unittest.main()
