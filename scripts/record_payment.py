#!/usr/bin/env python3
"""Record a verified processor payment exactly once.

The payment processor/webhook adapter should call this script only after it has
verified the provider signature/event authenticity.
"""
import argparse
import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
APEX_REVENUE_URL = os.getenv('APEX_REVENUE_URL', '').strip()
APEX_ADMIN_TOKEN = os.getenv('APEX_ADMIN_TOKEN', '').strip()
APEX_API_KEY = os.getenv('APEX_API_KEY', '').strip()
APEX_AUTH_MODE = os.getenv('APEX_AUTH_MODE', 'bearer').strip().lower()
APEX_PROPERTY_ID = os.getenv('APEX_PROPERTY_ID', '003').strip()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_apex_request(*, processor_event_id, amount, currency, processor, occurred_at):
    """Build a request for either the legacy APEX API or Supabase Edge runtime."""
    if not APEX_REVENUE_URL:
        return None

    if APEX_AUTH_MODE == 'supabase_edge':
        api_key = APEX_API_KEY or APEX_ADMIN_TOKEN
        if not api_key:
            return None
        payload = {
            'action': 'ingest_verified_revenue',
            'propertyId': APEX_PROPERTY_ID,
            'externalEventId': processor_event_id,
            'source': f'ai-revenue-agent:{processor}',
            'eventType': 'sale',
            'amountCents': int(round(amount * 100)),
            'currency': currency.upper(),
            'occurredAt': occurred_at,
            'verified': True,
        }
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json',
        }
    else:
        if not APEX_ADMIN_TOKEN:
            return None
        payload = {
            'id': processor_event_id,
            'propertyId': APEX_PROPERTY_ID,
            'source': f'ai-revenue-agent:{processor}',
            'type': 'sale',
            'amountCents': int(round(amount * 100)),
            'currency': currency.upper(),
            'occurredAt': occurred_at,
            'verified': True,
        }
        headers = {
            'Authorization': f'Bearer {APEX_ADMIN_TOKEN}',
            'Content-Type': 'application/json',
        }

    return urllib.request.Request(
        APEX_REVENUE_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST',
    )


def forward_to_apex(*, processor_event_id, amount, currency, processor, occurred_at):
    """Best-effort forward of already-verified revenue into APEX.

    Local payment recording remains the source transaction and must not fail
    just because APEX is unavailable.
    """
    request = build_apex_request(
        processor_event_id=processor_event_id,
        amount=amount,
        currency=currency,
        processor=processor,
        occurred_at=occurred_at,
    )
    if request is None:
        return {'enabled': False}

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode('utf-8') or '{}')
            return {'enabled': True, 'ok': 200 <= response.status < 300, 'response': body}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return {'enabled': True, 'ok': False, 'error': str(exc)}


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

    apex = forward_to_apex(
        processor_event_id=args.processor_event_id,
        amount=args.amount,
        currency=args.currency,
        processor=args.processor,
        occurred_at=ts,
    )
    print(json.dumps({'ok': True, 'duplicate': False, 'lead_id': args.lead_id,
                      'amount': args.amount, 'currency': args.currency.upper(), 'apex': apex}))


if __name__ == '__main__':
    main()
