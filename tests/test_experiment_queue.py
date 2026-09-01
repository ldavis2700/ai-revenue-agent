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


if __name__ == '__main__':
    unittest.main()
