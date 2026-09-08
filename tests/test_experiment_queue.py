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

    def test_overlapping_enqueues_preserve_one_active_experiment(self):
        for running in (False, True):
            with self.subTest(running=running):
                # Seed a different last_insert_rowid on the delayed connection.
                experiment_queue.enqueue_experiment(
                    self.conn, 'unrelated-' + str(running), 'Unrelated', 'rate', 1)
                model = 'overlap-' + str(running)
                other = experiment_queue.connect(self.path)
                winner = []
                base = self.conn

                class InterleavedConnection:
                    def execute(self, sql, parameters=()):
                        if sql.lstrip().startswith('INSERT') and not winner:
                            accepted = experiment_queue.enqueue_experiment(
                                other, model, 'Accepted hypothesis', 'rate', 0.2,
                                priority=5, max_cost=0, max_samples=10)
                            if running:
                                experiment_queue.start_experiment(other, accepted['id'])
                                accepted = {**dict(other.execute(
                                    'SELECT * FROM business_model_experiments WHERE id=?',
                                    (accepted['id'],)).fetchone()),
                                    'duplicate_active': False,
                                    'execution_gate': 'recommendation_only'}
                            winner.append(accepted)
                        return base.execute(sql, parameters)

                    def commit(self):
                        return base.commit()

                try:
                    delayed = experiment_queue.enqueue_experiment(
                        InterleavedConnection(), model, 'Stale hypothesis', 'rate', 0.5,
                        priority=99, max_cost=0, max_samples=50)
                    self.assertEqual(delayed, {**winner[0], 'duplicate_active': True})
                    count = self.conn.execute(
                        'SELECT COUNT(*) FROM business_model_experiments WHERE model_id=?',
                        (model,)).fetchone()[0]
                    self.assertEqual(count, 1)
                finally:
                    other.close()

    def test_new_experiment_allowed_after_previous_one_finishes(self):
        for cost in (0, 1):
            with self.subTest(cost=cost):
                model = 'finished-' + str(cost)
                first = experiment_queue.enqueue_experiment(
                    self.conn, model, 'First', 'rate', 0.1)
                experiment_queue.record_measurement(self.conn, first['id'], 0.2, cost)
                second = experiment_queue.enqueue_experiment(
                    self.conn, model, 'Second', 'rate', 0.3)
                self.assertNotEqual(first['id'], second['id'])
                self.assertFalse(second['duplicate_active'])
                self.assertEqual(second['hypothesis'], 'Second')
                self.assertEqual(second['status'], 'queued')

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

    def _assert_terminal_state_survives_interleaving(self, operation):
        # Pause immediately before a stale UPDATE, after its initial SELECT.
        # A second real SQLite connection records a terminal outcome first.
        scenarios = [(0.20, 0, 2, 'target_achieved'),
                     (0.02, 1, 2, 'cost_cap_exceeded'),
                     (0.02, 0, 20, 'sample_cap_reached_without_target')]
        for value, cost, samples, outcome in scenarios:
            with self.subTest(operation=operation, outcome=outcome):
                queued = experiment_queue.enqueue_experiment(
                    self.conn, operation + outcome, 'Bounded validation',
                    'conversion_rate', 0.10, max_cost=0, max_samples=20)
                other = experiment_queue.connect(self.path)
                self.addCleanup(other.close)
                terminal = []
                base = self.conn

                class InterleavedConnection:
                    def execute(self, sql, parameters=()):
                        if sql.lstrip().startswith('UPDATE') and not terminal:
                            terminal.append(experiment_queue.record_measurement(
                                other, queued['id'], value, cost, samples))
                        return base.execute(sql, parameters)

                    def commit(self):
                        return base.commit()

                connection = InterleavedConnection()
                if operation == 'start':
                    result = experiment_queue.start_experiment(connection, queued['id'])
                else:
                    result = experiment_queue.record_measurement(
                        connection, queued['id'], 0.01, 0, 1)
                self.assertEqual(len(terminal), 1)
                self.assertEqual(terminal[0]['outcome'], outcome)
                self.assertEqual(result, terminal[0])
                stored = dict(self.conn.execute(
                    'SELECT * FROM business_model_experiments WHERE id=?',
                    (queued['id'],)).fetchone())
                self.assertEqual(stored, {k: v for k, v in terminal[0].items()
                                          if k != 'execution_gate'})

    def test_stale_start_cannot_reopen_terminal_experiment(self):
        self._assert_terminal_state_survives_interleaving('start')

    def test_stale_measurement_cannot_reopen_terminal_experiment(self):
        self._assert_terminal_state_survives_interleaving('measurement')


if __name__ == '__main__':
    unittest.main()
