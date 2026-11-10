#!/usr/bin/env python3
"""Record delivery evidence for a legacy setup payment; never send or bill."""
import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone_required')
    return parsed


def validate_receipt(payment, receipt, now=None):
    """Validate recorded evidence, not independently attest a provider delivery."""
    if not payment or not receipt:
        return False
    now = now or datetime.now(timezone.utc)
    try:
        amount = float(payment['amount'])
        url = urlsplit(receipt['evidence_url'])
        completed = timestamp(receipt['completed_at'])
        paid = timestamp(payment['created_at'])
        return bool(
            math.isfinite(amount) and amount > 0
            and payment['processor'] not in ('test', 'sandbox')
            and receipt['lead_id'] == payment['lead_id']
            and receipt['processor_event_id'] == payment['processor_event_id']
            and re.fullmatch(r'[0-9a-f]{64}', receipt['artifact_sha256'])
            and url.scheme == 'https' and url.hostname
            and not url.username and not url.password
            and paid <= completed <= now
        )
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def payment_for(conn, lead_id, event_id):
    if not isinstance(lead_id, str) or not lead_id or not isinstance(event_id, str) or not event_id:
        return None
    try:
        row = conn.execute('''SELECT processor_event_id,lead_id,processor,amount,created_at
            FROM payment_events WHERE lead_id=? AND processor_event_id=?''',
            (lead_id, event_id)).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(zip(('processor_event_id', 'lead_id', 'processor', 'amount', 'created_at'), row)) if row else None


def delivery_complete(conn, lead_id, event_id):
    payment = payment_for(conn, lead_id, event_id)
    if payment is None:
        return False
    try:
        row = conn.execute('''SELECT lead_id,processor_event_id,artifact_sha256,evidence_url,completed_at
            FROM setup_delivery_receipts WHERE lead_id=? AND processor_event_id=?''',
            (lead_id, event_id)).fetchone()
    except sqlite3.OperationalError:
        return False
    receipt = dict(zip(('lead_id', 'processor_event_id', 'artifact_sha256', 'evidence_url', 'completed_at'), row)) if row else None
    return validate_receipt(payment, receipt)


def record_delivery(conn, lead_id, event_id, artifact_sha256, evidence_url, completed_at):
    receipt = dict(lead_id=lead_id, processor_event_id=event_id,
                   artifact_sha256=artifact_sha256, evidence_url=evidence_url,
                   completed_at=completed_at)
    with conn:
        if not validate_receipt(payment_for(conn, lead_id, event_id), receipt):
            raise ValueError('payment_linked_delivery_evidence_required')
        conn.execute('''CREATE TABLE IF NOT EXISTS setup_delivery_receipts (
            processor_event_id TEXT PRIMARY KEY, lead_id TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL, evidence_url TEXT NOT NULL,
            completed_at TEXT NOT NULL
        )''')
        values = (event_id, lead_id, artifact_sha256, evidence_url, completed_at)
        old = conn.execute('SELECT * FROM setup_delivery_receipts WHERE processor_event_id=?',
                           (event_id,)).fetchone()
        if old:
            if tuple(old) != values:
                raise ValueError('conflicting_delivery_receipt')
            return {'recorded': True, 'duplicate': True}
        conn.execute('INSERT INTO setup_delivery_receipts VALUES (?,?,?,?,?)', values)
    return {'recorded': True, 'duplicate': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lead_id')
    parser.add_argument('processor_event_id')
    parser.add_argument('--artifact', required=True, help='Delivered artifact whose SHA-256 is recorded')
    parser.add_argument('--evidence-url', required=True, help='HTTPS delivery receipt, not a promise of delivery')
    parser.add_argument('--completed-at', required=True, help='Timezone-aware actual delivery timestamp')
    args = parser.parse_args()
    with open(args.artifact, 'rb') as artifact:
        digest = hashlib.file_digest(artifact, 'sha256').hexdigest()
    path = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
    with sqlite3.connect('file:' + quote(os.path.abspath(path)) + '?mode=rw', uri=True) as conn:
        print(json.dumps(record_delivery(conn, args.lead_id, args.processor_event_id,
                                        digest, args.evidence_url, args.completed_at)))


if __name__ == '__main__':
    main()
