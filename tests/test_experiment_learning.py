import os
import sqlite3
import threading
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

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

    def _completed_experiment(self, model_id='atomic-model'):
        conn = experiment_queue.connect(self.path)
        try:
            queued = experiment_queue.enqueue_experiment(
                conn, model_id=model_id, hypothesis='measured demand',
                success_metric='conversion_rate', target_value=0.05,
                max_cost=0, max_samples=20)
            experiment_queue.start_experiment(conn, queued['id'])
            experiment_queue.record_measurement(
                conn, queued['id'], observed_value=0.1, observed_cost=0, sample_size=20)
            return queued
        finally:
            conn.close()

    def test_harvest_failure_rolls_back_observation_evidence_and_sync(self):
        self._completed_experiment()
        conn = mission_control.connect(self.path)
        mission_control.upsert_business_model_evidence(
            conn, 'atomic-model', observed_revenue=100, sample_size=10)
        before = dict(conn.execute('SELECT * FROM business_model_evidence').fetchone())
        conn.close()
        original = mission_control.upsert_business_model_evidence

        def fail_after_update(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('simulated interruption before sync marker')

        with patch.object(experiment_learning.mission_control,
                          'upsert_business_model_evidence', side_effect=fail_after_update):
            with self.assertRaisesRegex(RuntimeError, 'simulated interruption'):
                experiment_learning.harvest_completed_experiments(self.path)

        conn = mission_control.connect(self.path)
        self.assertEqual(dict(conn.execute('SELECT * FROM business_model_evidence').fetchone()), before)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM business_model_observations').fetchone()[0], 0)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM experiment_evidence_sync').fetchone()[0], 0)
        conn.close()
        retry = experiment_learning.harvest_completed_experiments(self.path)
        self.assertEqual(retry['processed'], 1)
        conn = experiment_observations.connect(self.path)
        self.assertEqual(len(experiment_observations.observation_history(conn, 'atomic-model')), 2)
        conn.close()

    def test_overlapping_harvests_serialize_before_appending_evidence(self):
        self._completed_experiment()
        entered, release = threading.Event(), threading.Event()
        original = experiment_learning.experiment_observations.append_observation
        calls = 0
        call_lock = threading.Lock()

        def pause_first_append(*args, **kwargs):
            nonlocal calls
            with call_lock:
                calls += 1
                first = calls == 1
            if first:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test append barrier timed out')
            return original(*args, **kwargs)

        with patch.object(experiment_learning.experiment_observations,
                          'append_observation', side_effect=pause_first_append):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(experiment_learning.harvest_completed_experiments, self.path)
                try:
                    self.assertTrue(entered.wait(5))
                    # A real independent writer must already be locked out before
                    # the first observation is appended, not only after insertion.
                    probe = sqlite3.connect(self.path, timeout=0.05)
                    try:
                        with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
                            probe.execute('BEGIN IMMEDIATE')
                    finally:
                        probe.rollback()
                        probe.close()
                    second_started = threading.Event()

                    def run_second():
                        second_started.set()
                        return experiment_learning.harvest_completed_experiments(self.path)

                    second = pool.submit(run_second)
                    self.assertTrue(second_started.wait(5))
                finally:
                    release.set()
                results = [first.result(timeout=5), second.result(timeout=5)]
        self.assertEqual(sorted(result['processed'] for result in results), [0, 1])
        conn = experiment_observations.connect(self.path)
        self.assertEqual(len(experiment_observations.observation_history(conn, 'atomic-model')), 1)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM experiment_evidence_sync').fetchone()[0], 1)
        self.assertEqual(conn.execute('SELECT sample_size FROM business_model_evidence').fetchone()[0], 20)
        conn.close()

    def _assert_invalid_harvest_is_atomic(self, field):
        with sqlite3.connect(self.path) as conn:
            before_evidence = conn.execute('SELECT * FROM business_model_evidence ORDER BY model_id').fetchall()
            before_experiments = conn.execute('SELECT * FROM business_model_experiments ORDER BY id').fetchall()
        with self.assertRaisesRegex(ValueError, field + ' must be finite'):
            experiment_learning.harvest_completed_experiments(self.path)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT * FROM business_model_evidence ORDER BY model_id').fetchall(), before_evidence)
            self.assertEqual(conn.execute('SELECT * FROM business_model_experiments ORDER BY id').fetchall(), before_experiments)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM business_model_observations').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM experiment_evidence_sync').fetchone()[0], 0)

    def test_nonfinite_legacy_evidence_is_not_sanitized_into_learning(self):
        # Direct writes represent pre-validation/imported rows. SQLite converts
        # a bound float NaN to NULL, so use its supported TEXT storage for NaN.
        fields = ('observed_revenue', 'observed_cost', 'conversion_rate', 'evidence_quality', 'sample_size')
        for field in fields:
            for invalid in (float('inf'), float('-inf'), 'NaN'):
                with self.subTest(field=field, invalid=invalid):
                    with tempfile.TemporaryDirectory() as directory:
                        self.path = os.path.join(directory, 'legacy.db')
                        self._completed_experiment('first-valid')
                        self._completed_experiment('legacy-invalid')
                        conn = mission_control.connect(self.path)
                        mission_control.upsert_business_model_evidence(conn, 'legacy-invalid', sample_size=10)
                        # field is a fixed local test allowlist, never external SQL.
                        conn.execute(f'UPDATE business_model_evidence SET {field}=? WHERE model_id=?',
                                     (invalid, 'legacy-invalid'))
                        conn.commit()
                        conn.close()
                        self._assert_invalid_harvest_is_atomic(field)

    def test_nonfinite_completed_measurements_are_not_sanitized_into_learning(self):
        for field, expected_field in (('observed_value', 'conversion_rate'),
                                      ('observed_cost', 'observed_cost'), ('sample_size', 'sample_size')):
            for invalid in (float('inf'), float('-inf'), 'NaN'):
                with self.subTest(field=field, invalid=invalid):
                    with tempfile.TemporaryDirectory() as directory:
                        self.path = os.path.join(directory, 'measurement.db')
                        mission_control.connect(self.path).close()
                        self._completed_experiment('first-valid')
                        bad = self._completed_experiment('measurement-invalid')
                        with sqlite3.connect(self.path) as conn:
                            conn.execute(f'UPDATE business_model_experiments SET {field}=? WHERE id=?',
                                         (invalid, bad['id']))
                        self._assert_invalid_harvest_is_atomic(expected_field)

    def test_finite_historical_bounds_remain_compatible(self):
        queued = self._completed_experiment('bounded-model')
        conn = mission_control.connect(self.path)
        mission_control.upsert_business_model_evidence(conn, 'bounded-model')
        conn.execute('''UPDATE business_model_evidence SET observed_revenue=-10,
            observed_cost=-2, conversion_rate=2, evidence_quality=2, sample_size=-4''')
        conn.execute('''UPDATE business_model_experiments SET observed_value=2,
            observed_cost=-1, sample_size=-2 WHERE id=?''', (queued['id'],))
        conn.commit()
        conn.close()
        self.assertEqual(experiment_learning.harvest_completed_experiments(self.path)['processed'], 1)
        conn = experiment_observations.connect(self.path)
        summary = experiment_observations.aggregate_observations(conn, 'bounded-model')
        conn.close()
        self.assertEqual(summary['observation_count'], 2)
        self.assertEqual(summary['observed_revenue'], 0)
        self.assertEqual(summary['observed_cost'], 0)
        self.assertEqual(summary['conversion_rate'], 1)
        self.assertEqual(summary['evidence_quality'], 0.5)
        self.assertEqual(summary['sample_size'], 0)


if __name__ == '__main__':
    unittest.main()
