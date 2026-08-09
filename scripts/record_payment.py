#!/usr/bin/env python3
"""Record a verified processor payment exactly once.

The payment processor/webhook adapter should call this script only after it has
verified the provider signature/event authenticity.
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('lead_id')
    parser.add_argument('processor_event_id')
    parser.add_argument('--amount', type=float, required=True)
    parser.add_argument('--currency', default='USD')
    parser.add_argument('--processor', default='external')
    parser.add_argument('--metadata', default='{}')
    args = parser.parse_args()

    metadata = json.loads(args.metadata)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS payment_events (
        processor_event_id TEXT PRIMARY KEY, lead_id TEXT, processor TEXT,
        amount REAL, currency TEXT, metadata TEXT, created_at TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT, event_type TEXT,
        value REAL DEFAULT 0, metadata TEXT, created_at TEXT
    )''')

    exists = conn.execute('SELECT 1 FROM payment_events WHERE processor_event_id=?',
                          (args.processor_event_id,)).fetchone()
    if exists:
        print(json.dumps({'ok': True, 'duplicate': True, 'processor_event_id': args.processor_event_id}))
        return

    ts = now_iso()
    conn.execute('INSERT INTO payment_events VALUES (?,?,?,?,?,?,?)',
                 (args.processor_event_id, args.lead_id, args.processor, args.amount,
                  args.currency.upper(), json.dumps(metadata), ts))
    conn.execute('INSERT INTO events (lead_id,event_type,value,metadata,created_at) VALUES (?,?,?,?,?)',
                 (args.lead_id, 'sale', args.amount, json.dumps({
                     'processor': args.processor,
                     'processor_event_id': args.processor_event_id,
                     'currency': args.currency.upper(),
                     **metadata,
                 }), ts))
    try:
        conn.execute('UPDATE leads SET status=?, updated_at=? WHERE id=?', ('won', ts, args.lead_id))
    except sqlite3.OperationalError:
        pass
    conn.commit()
    print(json.dumps({'ok': True, 'duplicate': False, 'lead_id': args.lead_id,
                      'amount': args.amount, 'currency': args.currency.upper()}))


if __name__ == '__main__':
    main()
