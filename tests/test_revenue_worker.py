import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from revenue_worker import RevenueWorker, STAGES, status


class RevenueWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name)/'revenue.db')
        env = patch.dict(os.environ, {'DELIVERY_ENABLED':'false', 'REVENUE_AGENT_KILL_SWITCH':'false',
                                     'REVENUE_AGENT_EXECUTION_ENABLED':'false'})
        env.start()
        self.addCleanup(env.stop)

    def worker(self, **kwargs):
        worker = RevenueWorker(self.path, **kwargs)
        self.addCleanup(worker.release)
        return worker

    def test_real_empty_account_repeats_without_income_or_end_date(self):
        worker = self.worker()
        waits = []
        def wait(seconds):
            waits.append(seconds)
            if len(waits) == 3:
                worker.stop.set()
        with patch.object(worker, 'wait', side_effect=wait), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(worker.run()['status'], 'stopped')
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revenue_worker_runs').fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM revenue_worker_runs WHERE status='completed'").fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM leads').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM agent_mission_runs').fetchone()[0], 3)
        self.assertEqual(waits, [900]*3)

    def test_stage_failure_does_not_starve_other_work(self):
        worker = self.worker()
        worker.acquire()
        calls = []
        def step(name, script):
            calls.append(name)
            if name == 'learn':
                raise RuntimeError('private secret')
            return {'stage':name, 'status':'completed'}
        with patch.object(worker, 'stage', side_effect=step):
            result = worker.cycle()
        self.assertEqual(calls, [s[0] for s in STAGES])
        self.assertEqual(result['status'], 'degraded')
        self.assertNotIn('private secret', json.dumps(result))

    def test_repeated_failure_retries_with_bounded_backoff(self):
        worker = self.worker(interval=900)
        waits = []
        def wait(seconds):
            waits.append(seconds)
            if len(waits) == 4:
                worker.stop.set()
        with patch.object(worker, 'cycle', return_value={'status':'degraded'}), \
                patch.object(worker, 'wait', side_effect=wait), contextlib.redirect_stdout(io.StringIO()):
            worker.run()
        self.assertEqual(waits, [1800,3600,3600,3600])

    def test_single_worker_lock_releases_for_restart(self):
        one, two = self.worker(), self.worker()
        self.assertTrue(one.acquire())
        self.assertFalse(two.acquire())
        one.release()
        self.assertTrue(two.acquire())

    def test_restart_marks_incomplete_cycle_interrupted(self):
        first = self.worker()
        first.acquire()
        with first.connect() as db:
            db.execute("INSERT INTO revenue_worker_runs (started_at,status) VALUES ('2026-01-01','running')")
        first.release()
        second = self.worker()
        second.acquire()
        with second.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM revenue_worker_runs').fetchone()[0], 'interrupted')

    def test_owner_pause_is_not_deleted_or_bypassed(self):
        worker = self.worker()
        worker.pause_file.touch()
        with patch.object(worker, 'cycle') as cycle:
            self.assertEqual(worker.run(once=True)['status'], 'paused')
        cycle.assert_not_called()
        self.assertTrue(worker.pause_file.exists())

    def test_pause_transition_interrupts_long_backoff_without_unpausing(self):
        worker = self.worker()
        heartbeats = []
        # The transition is simulated without removing or altering the
        # actual owner pause file or kill switch.
        with patch.object(worker, 'paused', side_effect=[False, False, True]), \
             patch.object(worker, 'heartbeat', side_effect=lambda state: heartbeats.append(state)), \
             patch.object(worker.stop, 'wait', return_value=False) as wait:
            worker.wait(3600)
        self.assertEqual(heartbeats, ['waiting', 'paused'])
        self.assertEqual(wait.call_count, 1)

    def test_resume_transition_interrupts_pause_sleep(self):
        worker = self.worker()
        heartbeats = []
        with patch.object(worker, 'paused', side_effect=[True, True, False]), \
             patch.object(worker, 'heartbeat', side_effect=lambda state: heartbeats.append(state)), \
             patch.object(worker.stop, 'wait', return_value=False) as wait:
            worker.wait(3600)
        self.assertEqual(heartbeats, ['paused', 'waiting'])
        self.assertEqual(wait.call_count, 1)

    def test_hung_stage_has_deadline_and_is_terminated(self):
        worker = self.worker(stage_timeout=1)
        worker.acquire()
        script = Path(self.tmp.name)/'hang.py'
        script.write_text('import time\ntime.sleep(30)\n')
        self.assertEqual(worker.stage('hang', str(script))['status'], 'timed_out')

    def test_stop_interrupts_running_stage(self):
        worker = self.worker(stage_timeout=30)
        worker.acquire()
        script = Path(self.tmp.name)/'hang.py'
        script.write_text('import time\ntime.sleep(30)\n')
        timer = threading.Timer(0.1, worker.stop.set)
        timer.start()
        try:
            self.assertEqual(worker.stage('hang', str(script))['status'], 'interrupted')
        finally:
            timer.cancel()

    def test_health_is_not_an_earnings_claim_and_stale_worker_is_unhealthy(self):
        worker = self.worker()
        worker.acquire()
        worker.heartbeat('waiting')
        self.assertTrue(status(self.path)['healthy'])
        self.assertNotIn('revenue', status(self.path))
        with worker.connect() as db:
            db.execute('UPDATE revenue_worker_health SET heartbeat_at=?',
                       ((datetime.now(timezone.utc)-timedelta(seconds=100)).isoformat(),))
        self.assertFalse(status(self.path)['healthy'])


if __name__ == '__main__':
    unittest.main()
