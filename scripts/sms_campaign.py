#!/usr/bin/env python3
"""Track manually-sent SMS campaigns without pretending we can read iPhone Messages.

Use this to register real outreach counts and response outcomes while keeping phone
numbers out of the repository. Runtime data lives in SQLite.
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS campaigns (
        id TEXT PRIMARY KEY, channel TEXT, offer TEXT, target_count INTEGER,
        sent_count INTEGER DEFAULT 0, replies INTEGER DEFAULT 0,
        interested INTEGER DEFAULT 0, sales INTEGER DEFAULT 0,
        revenue REAL DEFAULT 0, started_at TEXT, updated_at TEXT
    )''')
    return conn


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)

    start = sub.add_parser('start')
    start.add_argument('campaign_id')
    start.add_argument('--channel', default='sms')
    start.add_argument('--offer', default='AI Customer Response System - $100 one-time')
    start.add_argument('--target-count', type=int, required=True)
    start.add_argument('--sent-count', type=int, default=0)

    event = sub.add_parser('event')
    event.add_argument('campaign_id')
    event.add_argument('event_type', choices=['sent', 'reply', 'interested', 'sale'])
    event.add_argument('--count', type=int, default=1)
    event.add_argument('--value', type=float, default=0)

    report = sub.add_parser('report')
    report.add_argument('campaign_id')

    args = parser.parse_args()
    conn = connect()
    ts = now_iso()

    if args.command == 'start':
        conn.execute('''INSERT OR REPLACE INTO campaigns
            (id,channel,offer,target_count,sent_count,replies,interested,sales,revenue,started_at,updated_at)
            VALUES (?,?,?,?,?,0,0,0,0,?,?)''',
            (args.campaign_id, args.channel, args.offer, args.target_count, args.sent_count, ts, ts))
        conn.commit()

    elif args.command == 'event':
        column = {'sent':'sent_count','reply':'replies','interested':'interested','sale':'sales'}[args.event_type]
        conn.execute(f'UPDATE campaigns SET {column}={column}+?, updated_at=? WHERE id=?',
                     (args.count, ts, args.campaign_id))
        if args.event_type == 'sale':
            conn.execute('UPDATE campaigns SET revenue=revenue+? WHERE id=?', (args.value, args.campaign_id))
        conn.commit()

    row = conn.execute('SELECT * FROM campaigns WHERE id=?', (args.campaign_id,)).fetchone()
    if not row:
        raise SystemExit('campaign not found')
    keys = ['id','channel','offer','target_count','sent_count','replies','interested','sales','revenue','started_at','updated_at']
    data = dict(zip(keys, row))
    sent = data['sent_count'] or 0
    data['reply_rate'] = round(data['replies'] / sent, 4) if sent else 0
    data['close_rate'] = round(data['sales'] / sent, 4) if sent else 0
    data['revenue_per_contact'] = round(data['revenue'] / sent, 2) if sent else 0
    print(json.dumps(data))


if __name__ == '__main__':
    main()
