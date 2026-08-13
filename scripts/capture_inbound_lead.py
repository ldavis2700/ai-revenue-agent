#!/usr/bin/env python3
"""Validate and normalize an affirmative inbound lead for the revenue pipeline."""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def truthy(value):
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def normalize(payload):
    honeypot = str(payload.get('website_confirm') or '').strip()
    email = str(payload.get('contact_email') or payload.get('email') or '').strip().lower()
    company = str(payload.get('company_name') or payload.get('company') or '').strip()
    consent = truthy(payload.get('contact_consent'))
    privacy = truthy(payload.get('privacy_acknowledged'))
    errors = []
    if honeypot:
        errors.append('spam_check_failed')
    if not email or '@' not in email or email.startswith('@') or email.endswith('@'):
        errors.append('valid_contact_email_required')
    if not company:
        errors.append('company_name_required')
    if not consent:
        errors.append('affirmative_contact_consent_required')
    if not privacy:
        errors.append('privacy_acknowledgement_required')
    if errors:
        return None, errors

    lead_id = str(payload.get('id') or '').strip()
    if not lead_id:
        lead_id = 'in_' + hashlib.sha256(f'{email}|{company}'.encode()).hexdigest()[:16]
    return {
        'id': lead_id,
        'first_name': str(payload.get('first_name') or '').strip(),
        'last_name': str(payload.get('last_name') or '').strip(),
        'company_name': company,
        'contact_email': email,
        'industry': str(payload.get('industry') or '').strip(),
        'pain_point': str(payload.get('pain_point') or '').strip(),
        'website': str(payload.get('website') or '').strip(),
        'contact_allowed': True,
        'source': 'owned_inbound_opt_in',
        'metadata': {
            'consent_recorded_at': now_iso(),
            'consent_version': str(payload.get('consent_version') or 'contact-v1'),
            'campaign': str(payload.get('campaign') or '').strip(),
        },
    }, []


def record_intake(lead, path=DB_PATH):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute('''CREATE TABLE IF NOT EXISTS inbound_intake_audit (
        lead_id TEXT PRIMARY KEY, email_hash TEXT, source TEXT, consent_version TEXT,
        consent_recorded_at TEXT, received_at TEXT
    )''')
    email_hash = hashlib.sha256(lead['contact_email'].encode()).hexdigest()
    conn.execute('''INSERT OR REPLACE INTO inbound_intake_audit
        (lead_id,email_hash,source,consent_version,consent_recorded_at,received_at)
        VALUES (?,?,?,?,?,?)''', (
        lead['id'], email_hash, lead['source'], lead['metadata']['consent_version'],
        lead['metadata']['consent_recorded_at'], now_iso()))
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Capture a consented inbound business lead.')
    parser.add_argument('--json', help='Lead JSON; otherwise read JSON from stdin.')
    parser.add_argument('--no-persist', action='store_true')
    args = parser.parse_args()
    raw = args.json if args.json is not None else sys.stdin.read()
    try:
        payload = json.loads(raw or '{}')
    except json.JSONDecodeError:
        print(json.dumps({'accepted': False, 'errors': ['invalid_json']}))
        raise SystemExit(2)
    lead, errors = normalize(payload)
    if errors:
        print(json.dumps({'accepted': False, 'errors': errors}))
        raise SystemExit(2)
    if not args.no_persist:
        record_intake(lead)
    print(json.dumps({'accepted': True, 'leads': [lead]}))


if __name__ == '__main__':
    main()
