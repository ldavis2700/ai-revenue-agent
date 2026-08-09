#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description='Record a revenue lifecycle event for a lead.')
    parser.add_argument('lead_id')
    parser.add_argument('event_type', choices=['sent', 'delivered', 'reply', 'interested', 'not_interested', 'meeting', 'sale', 'refund', 'opt_out'])
    parser.add_argument('--value', type=float, default=0)
    parser.add_argument('--metadata', default='{}')
    args = parser.parse_args()

    metadata = json.loads(args.metadata)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT, event_type TEXT,
        value REAL DEFAULT 0, metadata TEXT, created_at TEXT
    )''')
    conn.execute('INSERT INTO events (lead_id,event_type,value,metadata,created_at) VALUES (?,?,?,?,?)',
                 (args.lead_id, args.event_type, args.value, json.dumps(metadata), now_iso()))

    status_map = {
        'sent': 'contacted',
        'reply': 'replied',
        'interested': 'interested',
        'not_interested': 'closed_lost',
        'meeting': 'meeting',
        'sale': 'won',
        'refund': 'refunded',
        'opt_out': 'suppressed',
    }
    if args.event_type in status_map:
        try:
            conn.execute('UPDATE leads SET status=?, updated_at=? WHERE id=?',
                         (status_map[args.event_type], now_iso(), args.lead_id))
        except sqlite3.OperationalError:
            pass
    conn.commit()

    totals = dict(conn.execute('''SELECT
        COALESCE(SUM(CASE WHEN event_type='sale' THEN value ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN event_type='refund' THEN value ELSE 0 END),0),
        COUNT(CASE WHEN event_type='sale' THEN 1 END)
        FROM events''').fetchone() and zip(
            ['gross_revenue', 'refunds', 'sales'],
            conn.execute('''SELECT
                COALESCE(SUM(CASE WHEN event_type='sale' THEN value ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN event_type='refund' THEN value ELSE 0 END),0),
                COUNT(CASE WHEN event_type='sale' THEN 1 END)
                FROM events''').fetchone()
        ))
    totals['net_revenue'] = totals['gross_revenue'] - totals['refunds']
    print(json.dumps({'ok': True, 'lead_id': args.lead_id, 'event_type': args.event_type, 'totals': totals}))


if __name__ == '__main__':
    main()
