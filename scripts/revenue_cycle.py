#!/usr/bin/env python3
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
MIN_SCORE = int(os.getenv('MIN_LEAD_SCORE', '55'))
MAX_OUTREACH = int(os.getenv('MAX_OUTREACH_PER_RUN', '20'))
OFFER_PRICE = os.getenv('OFFER_PRICE', '100')
OFFER_NAME = os.getenv('OFFER_NAME', 'AI Customer Response System')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def stable_id(lead):
    raw = (lead.get('contact_email') or '') + '|' + (lead.get('company_name') or '')
    return lead.get('id') or hashlib.sha256(raw.lower().encode()).hexdigest()[:16]


def normalize(lead):
    return {
        'id': stable_id(lead),
        'first_name': str(lead.get('first_name') or '').strip(),
        'last_name': str(lead.get('last_name') or '').strip(),
        'company_name': str(lead.get('company_name') or '').strip(),
        'contact_email': str(lead.get('contact_email') or '').strip().lower(),
        'industry': str(lead.get('industry') or '').strip(),
        'pain_point': str(lead.get('pain_point') or '').strip(),
        'website': str(lead.get('website') or '').strip(),
        'source': str(lead.get('source') or 'external').strip(),
        'contact_allowed': bool(lead.get('contact_allowed', False)),
        'metadata': lead.get('metadata') or {},
    }


def score_lead(lead):
    score, reasons = 0, []
    factors = [
        (lead['contact_email'] and '@' in lead['contact_email'], 25, 'valid email'),
        (lead['company_name'], 15, 'company identified'),
        (lead['pain_point'], 25, 'pain point identified'),
        (lead['industry'], 10, 'industry identified'),
        (lead['website'], 10, 'website available'),
        (lead['contact_allowed'], 15, 'contact permitted'),
    ]
    for present, points, reason in factors:
        if present:
            score += points
            reasons.append(reason)
    return min(score, 100), reasons


def build_outreach(lead, score):
    first = lead['first_name'] or 'there'
    company = lead['company_name'] or 'your business'
    pain = lead['pain_point'] or 'turning inquiries into paying customers faster'
    return {
        'subject': f'Idea for {company}',
        'body': (
            f'Hi {first},\n\nI came across {company} and noticed an opportunity around {pain}. '
            'I build simple AI-powered customer response systems for businesses that help respond faster, '
            'follow up consistently, and convert more inquiries into customers.\n\n'
            f'I can build a tailored {OFFER_NAME} for {company} for a one-time ${OFFER_PRICE}. '
            'If useful, I can show you exactly what I would build before you decide.\n\n'
            'Best,\nRMC Family Enterprises LLC'
        ),
        'score': score,
    }


def load_from_url(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'AI-Revenue-Agent/1.0'})
    token = os.getenv('LEADS_API_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = response.read().decode('utf-8')
        content_type = response.headers.get('Content-Type', '')
    if 'csv' in content_type or url.lower().endswith('.csv'):
        return list(csv.DictReader(io.StringIO(payload)))
    data = json.loads(payload)
    return data if isinstance(data, list) else data.get('leads', [])


def load_leads():
    if os.getenv('LEADS_JSON'):
        data = json.loads(os.environ['LEADS_JSON'])
        return data if isinstance(data, list) else data.get('leads', [])
    if os.getenv('LEADS_API_URL'):
        return load_from_url(os.environ['LEADS_API_URL'])
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            data = json.loads(raw)
            return data if isinstance(data, list) else data.get('leads', [])
    return []


def db_connect():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY, email TEXT, company TEXT, industry TEXT, pain_point TEXT,
        score INTEGER, contact_allowed INTEGER, source TEXT, status TEXT,
        outreach_subject TEXT, outreach_body TEXT, created_at TEXT, updated_at TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT, event_type TEXT,
        value REAL DEFAULT 0, metadata TEXT, created_at TEXT
    )''')
    return conn


def upsert_lead(conn, lead, score, outreach):
    timestamp = now_iso()
    existing = conn.execute('SELECT status, created_at FROM leads WHERE id=?', (lead['id'],)).fetchone()
    status = existing[0] if existing else ('qualified' if score >= MIN_SCORE else 'unqualified')
    created_at = existing[1] if existing else timestamp
    conn.execute('''INSERT OR REPLACE INTO leads
        (id,email,company,industry,pain_point,score,contact_allowed,source,status,outreach_subject,outreach_body,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        lead['id'], lead['contact_email'], lead['company_name'], lead['industry'], lead['pain_point'], score,
        int(lead['contact_allowed']), lead['source'], status, outreach['subject'], outreach['body'], created_at, timestamp
    ))
    if not existing:
        conn.execute('INSERT INTO events (lead_id,event_type,metadata,created_at) VALUES (?,?,?,?)',
                     (lead['id'], 'lead_created', json.dumps({'score': score}), timestamp))
    return status


def main():
    leads = [normalize(x) for x in load_leads()]
    conn = db_connect()
    actionable, drafts = [], []
    for lead in leads:
        score, reasons = score_lead(lead)
        outreach = build_outreach(lead, score)
        status = upsert_lead(conn, lead, score, outreach)
        item = {**lead, 'score': score, 'score_reasons': reasons, 'status': status, 'outreach': outreach}
        if score >= MIN_SCORE:
            drafts.append(item)
            if lead['contact_allowed'] and len(actionable) < MAX_OUTREACH:
                actionable.append(item)
    conn.commit()
    print(json.dumps({
        'metrics': {
            'processed': len(leads), 'qualified': len(drafts), 'contact_ready': len(actionable),
            'min_score': MIN_SCORE, 'max_outreach_per_run': MAX_OUTREACH, 'database': DB_PATH,
        },
        'contact_ready': actionable,
        'drafts': drafts,
    }))


if __name__ == '__main__':
    main()
