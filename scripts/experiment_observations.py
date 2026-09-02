#!/usr/bin/env python3
"""Append-only historical observations for APEX business-model experiments."""
from __future__ import annotations

import os
import math
import sqlite3
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS business_model_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL,
        experiment_id INTEGER,
        property_id TEXT,
        observed_revenue REAL NOT NULL DEFAULT 0,
        observed_cost REAL NOT NULL DEFAULT 0,
        conversion_rate REAL NOT NULL DEFAULT 0,
        evidence_quality REAL NOT NULL DEFAULT 0,
        sample_size REAL,
        source TEXT NOT NULL DEFAULT 'experiment',
        observed_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_business_model_observations_model_time ON business_model_observations(model_id, observed_at)')
    return conn


def _finite_float(value: float, field: str) -> float:
    """Reject non-finite evidence before clamping or writing immutable history."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{field} must be finite')
    return number


def _observation_timestamp(value: str | None, created_at: str) -> str:
    """Validate new evidence time and store one sortable UTC representation."""
    if value is None:
        value = created_at
    try:
        if not isinstance(value, str):
            raise ValueError('timestamp must be a string')
        observed = datetime.fromisoformat(value)
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError('timestamp must include a timezone')
        observed = observed.astimezone(timezone.utc)
        if observed > datetime.fromisoformat(created_at):
            raise ValueError('timestamp is in the future')
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('observed_at must be a timezone-aware ISO timestamp no later than now') from error
    return observed.isoformat()


def append_observation(conn: sqlite3.Connection, model_id: str, *, experiment_id: int | None = None,
                       property_id: str | None = None, observed_revenue: float = 0,
                       observed_cost: float = 0, conversion_rate: float = 0,
                       evidence_quality: float = 0, sample_size: float | None = None,
                       source: str = 'experiment', observed_at: str | None = None) -> dict[str, Any]:
    """Persist one immutable measured observation without overwriting prior evidence."""
    revenue = max(0.0, _finite_float(observed_revenue, 'observed_revenue'))
    cost = max(0.0, _finite_float(observed_cost, 'observed_cost'))
    conversion = min(1.0, max(0.0, _finite_float(conversion_rate, 'conversion_rate')))
    quality = min(1.0, max(0.0, _finite_float(evidence_quality, 'evidence_quality')))
    samples = None if sample_size is None else max(0.0, _finite_float(sample_size, 'sample_size'))
    created_at = now_iso()
    observed_at = _observation_timestamp(observed_at, created_at)
    conn.execute('''INSERT INTO business_model_observations
        (model_id,experiment_id,property_id,observed_revenue,observed_cost,conversion_rate,
         evidence_quality,sample_size,source,observed_at,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (model_id, experiment_id, property_id, revenue, cost, conversion, quality, samples,
         source, observed_at, created_at))
    conn.commit()
    row = conn.execute('SELECT * FROM business_model_observations WHERE id=last_insert_rowid()').fetchone()
    return dict(row)


def observation_history(conn: sqlite3.Connection, model_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        'SELECT * FROM business_model_observations WHERE model_id=? ORDER BY observed_at DESC, id DESC LIMIT ?',
        (model_id, max(1, int(limit))),
    ).fetchall()
    return [dict(row) for row in rows]


def aggregate_observations(conn: sqlite3.Connection, model_id: str) -> dict[str, Any]:
    rows = conn.execute(
        'SELECT * FROM business_model_observations WHERE model_id=? ORDER BY observed_at ASC, id ASC',
        (model_id,),
    ).fetchall()
    if not rows:
        return {
            'model_id': model_id,
            'observation_count': 0,
            'observed_revenue': 0.0,
            'observed_cost': 0.0,
            'conversion_rate': 0.0,
            'evidence_quality': 0.0,
            'sample_size': 0.0,
            'observed_at': None,
        }

    total_samples = sum(max(0.0, float(row['sample_size'] or 0)) for row in rows)
    if total_samples > 0:
        conversion_rate = sum(float(row['conversion_rate']) * max(0.0, float(row['sample_size'] or 0)) for row in rows) / total_samples
        evidence_quality = sum(float(row['evidence_quality']) * max(0.0, float(row['sample_size'] or 0)) for row in rows) / total_samples
    else:
        conversion_rate = sum(float(row['conversion_rate']) for row in rows) / len(rows)
        evidence_quality = sum(float(row['evidence_quality']) for row in rows) / len(rows)

    return {
        'model_id': model_id,
        'observation_count': len(rows),
        'observed_revenue': round(sum(float(row['observed_revenue']) for row in rows), 2),
        'observed_cost': round(sum(float(row['observed_cost']) for row in rows), 2),
        'conversion_rate': round(conversion_rate, 6),
        'evidence_quality': round(evidence_quality, 6),
        'sample_size': round(total_samples, 2),
        'observed_at': rows[-1]['observed_at'],
    }
