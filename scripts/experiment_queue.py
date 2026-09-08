#!/usr/bin/env python3
"""Durable, recommendation-only experiment queue for APEX business-model validation."""
from __future__ import annotations

import os
import math
import sqlite3
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
ACTIVE_STATES = {'queued', 'running'}
FINAL_STATES = {'completed', 'stopped'}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS business_model_experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL,
        hypothesis TEXT NOT NULL,
        success_metric TEXT NOT NULL,
        target_value REAL NOT NULL,
        priority INTEGER NOT NULL DEFAULT 100,
        max_cost REAL NOT NULL DEFAULT 0,
        max_samples REAL,
        status TEXT NOT NULL DEFAULT 'queued',
        observed_value REAL NOT NULL DEFAULT 0,
        observed_cost REAL NOT NULL DEFAULT 0,
        sample_size REAL NOT NULL DEFAULT 0,
        outcome TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT
    )''')
    return conn


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _finite_float(value: float, field: str) -> float:
    """Reject invalid measurements before bounds checks or persistent writes."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{field} must be finite')
    return number


def enqueue_experiment(conn: sqlite3.Connection, model_id: str, hypothesis: str,
                       success_metric: str, target_value: float, priority: int = 100,
                       max_cost: float = 0, max_samples: float | None = None) -> dict[str, Any]:
    """Queue one bounded experiment; never authorizes external execution or spend."""
    existing = conn.execute(
        "SELECT * FROM business_model_experiments WHERE model_id=? AND status IN ('queued','running') "
        "ORDER BY id DESC LIMIT 1", (model_id,)).fetchone()
    if existing is not None:
        return {**dict(existing), 'duplicate_active': True, 'execution_gate': 'recommendation_only'}

    target = _finite_float(target_value, 'target_value')
    cost_cap = max(0.0, _finite_float(max_cost, 'max_cost'))
    sample_cap = None if max_samples is None else max(0.0, _finite_float(max_samples, 'max_samples'))
    # The initial lookup is only a fast path. Check again in the write statement
    # so two connections cannot both enqueue an active experiment for this model.
    inserted = conn.execute('''INSERT INTO business_model_experiments
        (model_id,hypothesis,success_metric,target_value,priority,max_cost,max_samples,status,created_at)
        SELECT ?,?,?,?,?,?,?,'queued',?
        WHERE NOT EXISTS (
            SELECT 1 FROM business_model_experiments
            WHERE model_id=? AND status IN ('queued','running')
        )''',
        (model_id, hypothesis, success_metric, target, int(priority),
         cost_cap, sample_cap, now_iso(), model_id))
    duplicate = inserted.rowcount == 0
    # Read the selected row while the write transaction still holds its lock.
    if duplicate:
        row = conn.execute(
            "SELECT * FROM business_model_experiments WHERE model_id=? AND status IN ('queued','running') "
            "ORDER BY id DESC LIMIT 1", (model_id,)).fetchone()
    else:
        row = conn.execute('SELECT * FROM business_model_experiments WHERE id=?',
                           (inserted.lastrowid,)).fetchone()
    conn.commit()
    return {**dict(row), 'duplicate_active': duplicate, 'execution_gate': 'recommendation_only'}


def next_experiment(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM business_model_experiments WHERE status='queued' ORDER BY priority ASC, id ASC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {**dict(row), 'execution_gate': 'recommendation_only'}


def start_experiment(conn: sqlite3.Connection, experiment_id: int) -> dict[str, Any] | None:
    row = conn.execute('SELECT * FROM business_model_experiments WHERE id=?', (experiment_id,)).fetchone()
    if row is None:
        return None
    if row['status'] == 'queued':
        conn.execute("UPDATE business_model_experiments SET status='running', started_at=? "
                     "WHERE id=? AND status='queued'",
                     (now_iso(), experiment_id))
        conn.commit()
    row = conn.execute('SELECT * FROM business_model_experiments WHERE id=?', (experiment_id,)).fetchone()
    return {**dict(row), 'execution_gate': 'recommendation_only'}


def record_measurement(conn: sqlite3.Connection, experiment_id: int, observed_value: float,
                       observed_cost: float = 0, sample_size: float = 0) -> dict[str, Any] | None:
    """Record cumulative measured outcomes and enforce declared stopping rules."""
    row = conn.execute('SELECT * FROM business_model_experiments WHERE id=?', (experiment_id,)).fetchone()
    if row is None:
        return None
    if row['status'] in FINAL_STATES:
        return {**dict(row), 'execution_gate': 'recommendation_only'}

    value = _finite_float(observed_value, 'observed_value')
    cost = max(0.0, _finite_float(observed_cost, 'observed_cost'))
    samples = max(0.0, _finite_float(sample_size, 'sample_size'))
    status = 'running'
    outcome = None

    # max_cost=0 is an explicit zero-spend experiment, not an unlimited budget.
    if cost > row['max_cost']:
        status, outcome = 'stopped', 'cost_cap_exceeded'
    elif value >= row['target_value']:
        status, outcome = 'completed', 'target_achieved'
    elif row['max_samples'] is not None and samples >= row['max_samples']:
        status, outcome = 'completed', 'sample_cap_reached_without_target'

    completed_at = now_iso() if status in FINAL_STATES else None
    # Another connection may have finalized the experiment after our SELECT.
    # Keep the stopping decision and its evidence immutable in the UPDATE itself.
    conn.execute('''UPDATE business_model_experiments
        SET observed_value=?, observed_cost=?, sample_size=?, status=?, outcome=?, completed_at=?
        WHERE id=? AND status IN ('queued','running')''',
        (value, cost, samples, status, outcome, completed_at, experiment_id))
    conn.commit()
    updated = conn.execute('SELECT * FROM business_model_experiments WHERE id=?', (experiment_id,)).fetchone()
    return {**dict(updated), 'execution_gate': 'recommendation_only'}


def queue_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {row['status']: row['count'] for row in conn.execute(
        'SELECT status, COUNT(*) AS count FROM business_model_experiments GROUP BY status').fetchall()}
    return {
        'queued': counts.get('queued', 0),
        'running': counts.get('running', 0),
        'completed': counts.get('completed', 0),
        'stopped': counts.get('stopped', 0),
        'next': next_experiment(conn),
        'execution_gate': 'recommendation_only',
        'guardrails': {
            'automatic_spend': False,
            'automatic_outreach': False,
            'automatic_contracts': False,
            'automatic_charging': False,
            'automatic_production_deploy': False,
        },
    }
