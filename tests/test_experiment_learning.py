import os
import tempfile
import unittest

from scripts import experiment_learning, experiment_queue, mission_control


class ExperimentLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'agent.db')
        mission_control.connect(self.path).close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_completed_conversion_experiment_updates_evidence_once(self):
        conn = experiment_queue.connect(self.path)
        queued = experiment_queue.enqueue_experiment(
            conn,
            model_id='model-a',
            hypothesis='measurable demand',
            success_metric='conversion_rate',
            target_value=0.05,
            max_cost=0,
            max_samples=20,
        )
        experiment_queue.start_experiment(conn, queued['id'])
        measured = experiment_queue.record_measurement(
            conn, queued['id'], observed_value=0.08, observed_cost=0, sample_size=20)
        self.assertEqual(measured['status'], 'completed')
        conn.close()

        first = experiment_learning.harvest_completed_experiments(self.path)
        self.assertEqual(first['processed'], 1)
        self.assertFalse(first['external_actions_allowed'])

        mconn = mission_control.connect(self.path)
        row = mconn.execute('SELECT * FROM business_model_evidence WHERE model_id=?', ('model-a',)).fetchone()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row['conversion_rate'], 0.08)
        self.assertEqual(row['sample_size'], 20)
        self.assertEqual(row['evidence_quality'], 1.0)
        mconn.close()

        second = experiment_learning.harvest_completed_experiments(self.path)
        self.assertEqual(second['processed'], 0)

    def test_running_experiment_is_not_promoted(self):
        conn = experiment_queue.connect(self.path)
        queued = experiment_queue.enqueue_experiment(
            conn,
            model_id='model-b',
            hypothesis='still measuring',
            success_metric='conversion_rate',
            target_value=0.5,
            max_cost=0,
            max_samples=100,
        )
        experiment_queue.start_experiment(conn, queued['id'])
        experiment_queue.record_measurement(
            conn, queued['id'], observed_value=0.1, observed_cost=0, sample_size=5)
        conn.close()

        result = experiment_learning.harvest_completed_experiments(self.path)
        self.assertEqual(result['processed'], 0)
        mconn = mission_control.connect(self.path)
        row = mconn.execute('SELECT * FROM business_model_evidence WHERE model_id=?', ('model-b',)).fetchone()
        self.assertIsNone(row)
        mconn.close()


if __name__ == '__main__':
    unittest.main()
