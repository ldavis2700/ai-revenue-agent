#!/usr/bin/env python3
"""Continuously pursue revenue work; revenue totals never control continuation."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
STAGES = (
    ('learn', 'scripts/experiment_learning.py'),
    ('plan', 'scripts/mission_control.py'),
    ('execute_authorized_inbound', 'autonomous_cycle.py'),
)


def now():
    return datetime.now(timezone.utc).isoformat()


class RevenueWorker:
    def __init__(self, path, interval=900, stage_timeout=120, stop=None):
        self.path = str(Path(path).resolve())
        self.interval = interval
        self.stage_timeout = stage_timeout
        self.stop = stop or threading.Event()
        self.pause_file = Path(self.path + '.pause')
        self.lock = None

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def acquire(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = open(self.path + '.worker.lock', 'a+')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            self.lock = None
            return False
        try:
            # Initialize the existing revenue schema without loading remote leads.
            from scripts import revenue_cycle
            original = revenue_cycle.DB_PATH
            try:
                revenue_cycle.DB_PATH = self.path
                db = revenue_cycle.db_connect()
                db.commit()
                db.close()
            finally:
                revenue_cycle.DB_PATH = original
            with self.connect() as db:
                db.executescript('''
                    CREATE TABLE IF NOT EXISTS revenue_worker_health (
                        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                        state TEXT NOT NULL, stage TEXT, heartbeat_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS revenue_worker_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
                        finished_at TEXT, status TEXT NOT NULL, stages_json TEXT
                    );
                ''')
                db.execute("UPDATE revenue_worker_runs SET status='interrupted', finished_at=? WHERE status='running'", (now(),))
            self.heartbeat('starting')
            return True
        except BaseException:
            self.release()
            raise

    def release(self):
        if self.lock:
            fcntl.flock(self.lock, fcntl.LOCK_UN)
            self.lock.close()
            self.lock = None

    def paused(self):
        return (self.pause_file.exists()
                or os.getenv('REVENUE_AGENT_KILL_SWITCH', 'false').lower() == 'true')

    def heartbeat(self, state, stage=None):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO revenue_worker_health VALUES (1,?,?,?)',
                       (state, stage, now()))

    def stage(self, name, script):
        # Fixed local scripts only. No arbitrary commands from customers or feeds.
        env = {**os.environ, 'REVENUE_DB_PATH': self.path}
        process = subprocess.Popen([sys.executable, str(ROOT / script)], cwd=ROOT,
                                   env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        deadline = time.monotonic() + self.stage_timeout
        try:
            while process.poll() is None:
                if self.stop.is_set() or self.paused():
                    return {'stage': name, 'status': 'interrupted'}
                if time.monotonic() >= deadline:
                    return {'stage': name, 'status': 'timed_out'}
                self.heartbeat('working', name)
                self.stop.wait(min(1, max(0, deadline-time.monotonic())))
            return {'stage': name, 'status': 'completed' if process.returncode == 0 else 'failed'}
        finally:
            if process.poll() is None:
                # Terminate this stage's descendants too; do not leave senders running.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()

    def cycle(self):
        with self.connect() as db:
            run_id = db.execute("INSERT INTO revenue_worker_runs (started_at,status) VALUES (?,'running')", (now(),)).lastrowid
        results = []
        for name, script in STAGES:
            if self.stop.is_set() or self.paused():
                break
            try:
                results.append(self.stage(name, script))
            except Exception:
                # Keep the other stages moving; never log credentials or customer data.
                results.append({'stage': name, 'status': 'failed'})
        status = ('interrupted' if len(results) != len(STAGES) or any(r['status']=='interrupted' for r in results)
                  else 'completed' if all(r['status']=='completed' for r in results) else 'degraded')
        with self.connect() as db:
            db.execute('UPDATE revenue_worker_runs SET finished_at=?,status=?,stages_json=? WHERE id=?',
                       (now(), status, json.dumps(results), run_id))
            db.execute('DELETE FROM revenue_worker_runs WHERE id NOT IN (SELECT id FROM revenue_worker_runs ORDER BY id DESC LIMIT 1000)')
        self.heartbeat('idle')
        return {'run_id': run_id, 'status': status, 'stages': results}

    def wait(self, seconds):
        """Wake promptly when the owner pauses or resumes, not after the backoff.

        Never remove a pause file or override the kill switch. A transition
        returns control to run(), which rechecks authoritative stop controls.
        """
        deadline = time.monotonic() + seconds
        initial_pause = self.paused()
        while not self.stop.is_set() and time.monotonic() < deadline:
            current_pause = self.paused()
            self.heartbeat('paused' if current_pause else 'waiting')
            if current_pause != initial_pause:
                return
            self.stop.wait(min(15, max(0, deadline-time.monotonic())))

    def run(self, once=False):
        if not self.acquire():
            return {'status': 'already_running'}
        failures = 0
        try:
            # Deliberately no target earnings, completion count, or end date.
            while not self.stop.is_set():
                if self.paused():
                    self.heartbeat('paused')
                    if once:
                        return {'status': 'paused'}
                    self.wait(15)
                    continue
                try:
                    result = self.cycle()
                except Exception:
                    result = {'status': 'degraded', 'reason': 'cycle_unavailable'}
                print(json.dumps(result), flush=True)
                if once:
                    return result
                failures = min(failures + 1, 6) if result['status'] == 'degraded' else 0
                # Bounded recovery delay; zero revenue and idle queues never stop work.
                self.wait(min(3600, self.interval * (2 ** failures)))
            return {'status': 'stopped'}
        finally:
            try:
                self.heartbeat('stopped')
            finally:
                self.release()


def status(path):
    from urllib.parse import quote
    with sqlite3.connect('file:' + quote(str(Path(path).resolve())) + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT state,stage,heartbeat_at FROM revenue_worker_health WHERE singleton=1').fetchone()
        if not row:
            return {'state': 'not_started', 'healthy': False}
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(row[2])).total_seconds()
        return {'state': row[0], 'stage': row[1], 'heartbeat_at': row[2],
                'healthy': row[0] not in ('stopped', 'paused') and 0 <= age < 90}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--db', default=os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db'))
    parser.add_argument('--interval', type=int, default=900)
    parser.add_argument('--stage-timeout', type=int, default=120)
    args = parser.parse_args()
    if not 10 <= args.interval <= 3600 or not 1 <= args.stage_timeout <= 600:
        parser.error('interval must be 10..3600 seconds and stage-timeout 1..600 seconds')
    if args.status:
        try:
            result = status(args.db)
        except sqlite3.Error:
            result = {'state': 'unavailable', 'healthy': False}
        print(json.dumps(result))
        return 0 if result['healthy'] else 1
    worker = RevenueWorker(args.db, args.interval, args.stage_timeout)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: worker.stop.set())
    result = worker.run(args.once)
    return 1 if args.once and result['status'] == 'degraded' else 0


if __name__ == '__main__':
    sys.exit(main())
