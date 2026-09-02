#!/usr/bin/env python3
"""Fold completed zero-cost experiment measurements back into APEX business-model evidence."""
from __future__ import annotations

import json
import os
import sys
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import experiment_observations
import experiment_queue
import mission_control

DB_PATH = os.getenv('REVENUE_DB_PATH', mission_control.DB_PATH)


def _ensure_sync_table(conn) -> None:
    conn.execute('''CREATE TABLE IF NOT EXISTS experiment_evidence_sync (
        experiment_id INTEGER PRIMARY KEY,
        synced_at TEXT NOT NULL
    )''')
    conn.commit()


def _existing_evidence(conn, model_id: str) -> dict[str, Any]:
    row = conn.execute('SELECT * FROM business_model_evidence WHERE model_id=?', (model_id,)).fetchone()
    return dict(row) if row is not None else {}


def _seed_legacy_evidence_if_needed(mconn, oconn, model_id: str) -> None:
    """Preserve pre-ledger aggregate evidence before observations become authoritative."""
    history = experiment_observations.observation_history(oconn, model_id, limit=1)
    if history:
        return
    prior = _existing_evidence(mconn, model_id)
    if not prior:
        return
    experiment_observations.append_observation(
        oconn,
        model_id,
        observed_revenue=max(0.0, float(prior.get('observed_revenue') or 0)),
        observed_cost=max(0.0, float(prior.get('observed_cost') or 0)),
        conversion_rate=min(1.0, max(0.0, float(prior.get('conversion_rate') or 0))),
        evidence_quality=min(1.0, max(0.0, float(prior.get('evidence_quality') or 0))),
        sample_size=None if prior.get('sample_size') is None else max(0.0, float(prior.get('sample_size') or 0)),
        source='legacy_evidence_seed',
        observed_at=prior.get('observed_at') or mission_control.now_iso(),
        commit=False,
    )


def harvest_completed_experiments(path: str = DB_PATH) -> dict[str, Any]:
    """Promote measured conversion evidence from completed experiments exactly once."""
    mconn = mission_control.connect(path)
    try:
        # Initialize shared schemas before taking the write lock. Every harvest
        # read/write below uses one connection and one transaction.
        experiment_queue.connect(path).close()
        experiment_observations.connect(path).close()
        _ensure_sync_table(mconn)
        mconn.execute('BEGIN IMMEDIATE')
        rows = mconn.execute('''SELECT e.* FROM business_model_experiments e
            LEFT JOIN experiment_evidence_sync s ON s.experiment_id=e.id
            WHERE e.status='completed' AND e.success_metric='conversion_rate' AND s.experiment_id IS NULL
            ORDER BY e.id ASC''').fetchall()
        processed = []
        for row in rows:
            item = dict(row)
            _seed_legacy_evidence_if_needed(mconn, mconn, item['model_id'])

            # Crash-safe idempotency: if the immutable observation already exists, reuse it
            # rather than duplicating evidence before the sync marker is written.
            existing = mconn.execute(
                "SELECT id FROM business_model_observations WHERE experiment_id=? AND source='completed_experiment' LIMIT 1",
                (item['id'],),
            ).fetchone()
            if existing is None:
                samples = max(0.0, float(item.get('sample_size') or 0))
                experiment_observations.append_observation(
                    mconn,
                    item['model_id'],
                    experiment_id=item['id'],
                    observed_cost=max(0.0, float(item.get('observed_cost') or 0)),
                    conversion_rate=min(1.0, max(0.0, float(item.get('observed_value') or 0))),
                    evidence_quality=min(1.0, samples / 20.0),
                    sample_size=samples,
                    source='completed_experiment',
                    observed_at=item.get('completed_at') or mission_control.now_iso(),
                    commit=False,
                )

            aggregate = experiment_observations.aggregate_observations(mconn, item['model_id'])
            mission_control.upsert_business_model_evidence(
                mconn,
                item['model_id'],
                observed_revenue=aggregate['observed_revenue'],
                observed_cost=aggregate['observed_cost'],
                conversion_rate=aggregate['conversion_rate'],
                evidence_quality=aggregate['evidence_quality'],
                sample_size=aggregate['sample_size'],
                observed_at=aggregate['observed_at'] or mission_control.now_iso(),
                commit=False,
            )
            mconn.execute('INSERT INTO experiment_evidence_sync (experiment_id,synced_at) VALUES (?,?)',
                          (item['id'], mission_control.now_iso()))
            processed.append({
                'experiment_id': item['id'],
                'model_id': item['model_id'],
                'observation_count': aggregate['observation_count'],
            })
        mconn.commit()
        return {
            'processed': len(processed),
            'experiments': processed,
            'execution_gate': 'internal_learning_only',
            'external_actions_allowed': False,
        }
    except Exception:
        mconn.rollback()
        raise
    finally:
        mconn.close()


if __name__ == '__main__':
    print(json.dumps(harvest_completed_experiments(), indent=2))
