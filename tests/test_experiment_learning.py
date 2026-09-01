import os
import tempfile
import unittest

from scripts import experiment_learning, experiment_observations, experiment_queue, mission_control


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

        oconn = experiment_observations.connect(self.path)
        history = experiment_observations.observation_history(oconn, 'model-a')
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['experiment_id'], queued['id'])
        self.assertEqual(history[0]['source'], 'completed_experiment')
        oconn.close()

        second = experiment_learning.harvest_completed_experiments(self.path)
        self.assertEqual(second['processed'], 0)
        oconn = experiment_observations.connect(self.path)
        self.assertEqual(len(experiment_observations.observation_history(oconn, 'model-a')), 1)
        oconn.close()

    def test_legacy_evidence_is_seeded_before_new_experiment_history(self):
        mconn = mission_control.connect(self.path)
        mission_control.upsert_business_model_evidence(
            mconn,
            'model-c',
            observed_revenue=100,
            observed_cost=5,
            conversion_rate=0.20,
            evidence_quality=0.5,
            sample_size=10,
            observed_at=mission_control.now_iso(),
        )
        mconn.close()

        conn = experiment_queue.connect(self.path)
        queued = experiment_queue.enqueue_experiment(
            conn,
            model_id='model-c',
            hypothesis='new measured demand',
            success_metric='conversion_rate',
            target_value=0.10,
            max_cost=0,
            max_samples=10,
        )
        experiment_queue.start_experiment(conn, queued['id'])
        experiment_queue.record_measurement(
            conn, queued['id'], observed_value=0.10, observed_cost=0, sample_size=10)
        conn.close()

        result = experiment_learning.harvest_completed_experiments(self.path)
        self.assertEqual(result['processed'], 1)

        oconn = experiment_observations.connect(self.path)
        history = experiment_observations.observation_history(oconn, 'model-c')
        self.assertEqual(len(history), 2)
        self.assertEqual({row['source'] for row in history}, {'legacy_evidence_seed', 'completed_experiment'})
        aggregate = experiment_observations.aggregate_observations(oconn, 'model-c')
        self.assertAlmostEqual(aggregate['conversion_rate'], 0.15)
        self.assertEqual(aggregate['observed_revenue'], 100)
        self.assertEqual(aggregate['observed_cost'], 5)
        self.assertEqual(aggregate['sample_size'], 20)
        oconn.close()

        mconn = mission_control.connect(self.path)
        row = mconn.execute('SELECT * FROM business_model_evidence WHERE model_id=?', ('model-c',)).fetchone()
        self.assertAlmostEqual(row['conversion_rate'], 0.15)
        self.assertEqual(row['observed_revenue'], 100)
        self.assertEqual(row['observed_cost'], 5)
        self.assertEqual(row['sample_size'], 20)
        mconn.close()

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
