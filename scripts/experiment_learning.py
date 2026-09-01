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


def harvest_completed_experiments(path: str = DB_PATH) -> dict[str, Any]:
    """Promote measured conversion evidence from completed experiments exactly once."""
    mconn = mission_control.connect(path)
    qconn = experiment_queue.connect(path)
    try:
        _ensure_sync_table(mconn)
        rows = qconn.execute('''SELECT e.* FROM business_model_experiments e
            LEFT JOIN experiment_evidence_sync s ON s.experiment_id=e.id
            WHERE e.status='completed' AND e.success_metric='conversion_rate' AND s.experiment_id IS NULL
            ORDER BY e.id ASC''').fetchall()
        processed = []
        for row in rows:
            item = dict(row)
            prior = _existing_evidence(mconn, item['model_id'])
            prior_samples = max(0.0, float(prior.get('sample_size') or 0))
            new_samples = max(0.0, float(item.get('sample_size') or 0))
            total_samples = prior_samples + new_samples
            prior_rate = min(1.0, max(0.0, float(prior.get('conversion_rate') or 0)))
            new_rate = min(1.0, max(0.0, float(item.get('observed_value') or 0)))
            if total_samples > 0:
                combined_rate = ((prior_rate * prior_samples) + (new_rate * new_samples)) / total_samples
            else:
                combined_rate = max(prior_rate, new_rate)
            quality = max(
                min(1.0, max(0.0, float(prior.get('evidence_quality') or 0))),
                min(1.0, total_samples / 20.0),
            )
            mission_control.upsert_business_model_evidence(
                mconn,
                item['model_id'],
                observed_revenue=max(0.0, float(prior.get('observed_revenue') or 0)),
                observed_cost=max(0.0, float(prior.get('observed_cost') or 0)) + max(0.0, float(item.get('observed_cost') or 0)),
                conversion_rate=combined_rate,
                evidence_quality=quality,
                sample_size=total_samples,
                observed_at=item.get('completed_at') or mission_control.now_iso(),
            )
            mconn.execute('INSERT INTO experiment_evidence_sync (experiment_id,synced_at) VALUES (?,?)',
                          (item['id'], mission_control.now_iso()))
            mconn.commit()
            processed.append({'experiment_id': item['id'], 'model_id': item['model_id']})
        return {
            'processed': len(processed),
            'experiments': processed,
            'execution_gate': 'internal_learning_only',
            'external_actions_allowed': False,
        }
    finally:
        qconn.close()
        mconn.close()


if __name__ == '__main__':
    print(json.dumps(harvest_completed_experiments(), indent=2))
