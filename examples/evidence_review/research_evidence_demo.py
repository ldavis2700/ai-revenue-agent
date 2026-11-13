"""Small offline evidence-review demonstration. No buyer data, network, or production writes.

The SQLite store is a disposable LOCAL stand-in for a future buyer-approved Supabase
sandbox. A human must separately approve each proposed value before export.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    record_id TEXT PRIMARY KEY,
    field_name TEXT NOT NULL,
    proposed_value TEXT NOT NULL,
    source_label TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','corrected','rejected')),
    accepted_value TEXT,
    reviewer TEXT,
    CHECK ((review_status = 'pending' AND accepted_value IS NULL AND reviewer IS NULL)
        OR (review_status = 'rejected' AND accepted_value IS NULL AND reviewer IS NOT NULL)
        OR (review_status IN ('approved','corrected') AND accepted_value IS NOT NULL AND reviewer IS NOT NULL))
);
"""


def _validated_text(value: Any, label: str, maxlen: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maxlen:
        raise ValueError(f'{label} must be a nonempty string of at most {maxlen} characters')
    if '\x00' in value:
        raise ValueError(f'{label} contains a forbidden NUL character')
    return value.strip()


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def evidence_hash(source_label: str, excerpt: str) -> str:
    packed = json.dumps({'source': source_label, 'excerpt': excerpt}, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(packed.encode('utf-8')).hexdigest()


def ingest(db: sqlite3.Connection, records: list[dict[str, Any]]) -> int:
    """Queue evidence-backed proposals; changed evidence cannot overwrite a review."""
    if len(records) > 100:
        raise ValueError('Limit ingestion to 100 records per demonstration')
    validated = []
    ids: set[str] = set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError('Each record must be an object')
        rec_id = _validated_text(row.get('record_id'), 'record_id', 80)
        if rec_id in ids:
            raise ValueError('Duplicate record_id in input')
        ids.add(rec_id)
        field = _validated_text(row.get('field_name'), 'field_name', 100)
        proposed = _validated_text(row.get('proposed_value'), 'proposed_value', 1000)
        source = _validated_text(row.get('source_label'), 'source_label', 200)
        excerpt = _validated_text(row.get('excerpt'), 'excerpt', 2000)
        validated.append((rec_id, field, proposed, source, excerpt, evidence_hash(source, excerpt)))

    with db:
        for rec_id, field, proposed, source, excerpt, sha in validated:
            prev = db.execute('SELECT field_name, proposed_value, source_label, excerpt, evidence_sha256 FROM proposals WHERE record_id=?', (rec_id,)).fetchone()
            if prev:
                if tuple(prev) != (field, proposed, source, excerpt, sha):
                    raise ValueError(f'Existing record {rec_id} differs: manual reconciliation required')
            else:
                db.execute('INSERT INTO proposals (record_id,field_name,proposed_value,source_label,excerpt,evidence_sha256) VALUES (?,?,?,?,?,?)', (rec_id, field, proposed, source, excerpt, sha))
    return len(validated)


def review(db: sqlite3.Connection, record_id: str, decision: str, reviewer: str, corrected_value: str | None = None) -> dict:
    """Requires explicit human operator action. There is no auto-approval path."""
    record_id = _validated_text(record_id, 'record_id', 80)
    reviewer = _validated_text(reviewer, 'reviewer', 100)
    if decision not in ('approve', 'correct', 'reject'):
        raise ValueError('Decision must be approve, correct, or reject')
    if decision == 'correct':
        corrected_value = _validated_text(corrected_value, 'corrected_value', 1000)
    elif corrected_value is not None:
        raise ValueError('A corrected value is only valid for a correct decision')
    with db:
        old = db.execute('SELECT review_status,proposed_value,accepted_value,reviewer FROM proposals WHERE record_id=?', (record_id,)).fetchone()
        if old is None:
            raise ValueError('Unknown record; ingest evidence first')
        accepted = old['proposed_value'] if decision == 'approve' else (corrected_value if decision == 'correct' else None)
        status = {'approve':'approved','correct':'corrected','reject':'rejected'}[decision]
        if old['review_status'] != 'pending':
            if old['review_status'] == status and old['accepted_value'] == accepted and old['reviewer'] == reviewer:
                return {'record_id': record_id, 'status': status, 'idempotent': True}
            raise ValueError('Already reviewed; immutable decision requires a new record')
        db.execute('UPDATE proposals SET review_status=?,accepted_value=?,reviewer=? WHERE record_id=? AND review_status=?',
                   (status, accepted, reviewer, record_id, 'pending'))
    return {'record_id': record_id, 'status': status, 'idempotent': False}


def pending(db: sqlite3.Connection) -> list[dict]:
    return [dict(x) for x in db.execute('SELECT record_id, field_name, proposed_value, source_label, excerpt, evidence_sha256 FROM proposals WHERE review_status=? ORDER BY record_id', ('pending',))]


def approved_export(db: sqlite3.Connection) -> list[dict]:
    """Approved-only records; explicitly not a live Supabase export or payment."""
    return [dict(x) for x in db.execute("""SELECT record_id, field_name, accepted_value, source_label,
        evidence_sha256, review_status, reviewer FROM proposals
        WHERE review_status IN ('approved','corrected') ORDER BY record_id""")]


def main() -> None:
    parser = argparse.ArgumentParser(description='Offline evidence-to-review pilot (LOCAL ONLY).')
    parser.add_argument('--db', required=True, type=Path, help='Local disposable .sqlite database')
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('ingest')
    s.add_argument('--input', type=Path, required=True)
    s = sub.add_parser('review')
    s.add_argument('--record-id', required=True)
    s.add_argument('--decision', required=True, choices=['approve','correct','reject'])
    s.add_argument('--reviewer', required=True)
    s.add_argument('--corrected-value')
    sub.add_parser('pending')
    sub.add_parser('export')
    opts = parser.parse_args()
    with connect(opts.db) as db:
        if opts.command == 'ingest':
            if opts.input.stat().st_size > 1024 * 1024:
                parser.error('Input must be at most 1 MB')
            payload = json.loads(opts.input.read_text(encoding='utf-8'))
            if not isinstance(payload, list):
                parser.error('Input must be a JSON array')
            output = {'ingested': ingest(db, payload), 'new_pending': len(pending(db)), 'remote_writes': 0}
        elif opts.command == 'review':
            output = review(db, opts.record_id, opts.decision, opts.reviewer, opts.corrected_value)
        elif opts.command == 'pending':
            output = pending(db)
        else:
            output = {'approved_only': approved_export(db), 'remote_writes': 0,
                      'note': 'Local SQLite demonstration; separately approved Supabase test handoff is NOT implemented'}
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
