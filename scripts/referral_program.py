#!/usr/bin/env python3
"""Referral and partner attribution for the AI Revenue Agent.

The referral program is intentionally disabled by default. Enabling it only
allows attribution/tracking; this module never sends outreach, creates payouts,
or changes pricing on its own.
"""
import argparse
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
PROGRAM_ENABLED = os.getenv('REFERRAL_PROGRAM_ENABLED', 'false').strip().lower() in {'1', 'true', 'yes', 'on'}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS referral_partners (
        code TEXT PRIMARY KEY,
        partner_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS referral_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        lead_id TEXT,
        event_type TEXT NOT NULL,
        value REAL NOT NULL DEFAULT 0,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        UNIQUE(code, lead_id, event_type)
    )''')
    return conn


def require_enabled():
    if not PROGRAM_ENABLED:
        raise SystemExit('Referral program is disabled. Set REFERRAL_PROGRAM_ENABLED=true to use write actions.')


def generate_code():
    return secrets.token_urlsafe(8).replace('-', '').replace('_', '')[:10].upper()


def create_partner(args):
    require_enabled()
    conn = connect()
    code = (args.code or generate_code()).strip().upper()
    ts = now_iso()
    metadata = json.loads(args.metadata)
    conn.execute('''INSERT INTO referral_partners
        (code, partner_name, status, metadata, created_at, updated_at)
        VALUES (?, ?, 'active', ?, ?, ?)''',
        (code, args.partner_name.strip(), json.dumps(metadata), ts, ts))
    conn.commit()
    print(json.dumps({'ok': True, 'program_enabled': True, 'code': code, 'partner_name': args.partner_name.strip()}))


def record_event(args):
    require_enabled()
    if args.event_type not in {'click', 'lead', 'meeting', 'sale'}:
        raise SystemExit('event_type must be one of: click, lead, meeting, sale')
    conn = connect()
    code = args.code.strip().upper()
    partner = conn.execute('SELECT partner_name, status FROM referral_partners WHERE code=?', (code,)).fetchone()
    if not partner or partner[1] != 'active':
        raise SystemExit('Unknown or inactive referral code')
    metadata = json.loads(args.metadata)
    cur = conn.execute('''INSERT OR IGNORE INTO referral_events
        (code, lead_id, event_type, value, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (code, args.lead_id or None, args.event_type, args.value, json.dumps(metadata), now_iso()))
    conn.commit()
    print(json.dumps({
        'ok': True,
        'duplicate': cur.rowcount == 0,
        'code': code,
        'partner_name': partner[0],
        'event_type': args.event_type,
        'lead_id': args.lead_id or None,
        'value': args.value,
    }))


def report(_args):
    conn = connect()
    partners = conn.execute('SELECT COUNT(*) FROM referral_partners WHERE status="active"').fetchone()[0]
    row = conn.execute('''SELECT
        SUM(CASE WHEN event_type='click' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type='lead' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type='meeting' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type='sale' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type='sale' THEN value ELSE 0 END)
        FROM referral_events''').fetchone()
    clicks, leads, meetings, sales, revenue = [x or 0 for x in row]
    print(json.dumps({
        'ok': True,
        'program_enabled': PROGRAM_ENABLED,
        'active_partners': partners,
        'clicks': clicks,
        'leads': leads,
        'meetings': meetings,
        'sales': sales,
        'attributed_revenue': revenue,
        'payouts_enabled': False,
    }))


def build_parser():
    parser = argparse.ArgumentParser(description='Disabled-by-default referral attribution loop')
    sub = parser.add_subparsers(dest='command', required=True)

    create = sub.add_parser('create-partner')
    create.add_argument('partner_name')
    create.add_argument('--code')
    create.add_argument('--metadata', default='{}')
    create.set_defaults(func=create_partner)

    event = sub.add_parser('record')
    event.add_argument('code')
    event.add_argument('event_type')
    event.add_argument('--lead-id', default='')
    event.add_argument('--value', type=float, default=0)
    event.add_argument('--metadata', default='{}')
    event.set_defaults(func=record_event)

    rpt = sub.add_parser('report')
    rpt.set_defaults(func=report)
    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
