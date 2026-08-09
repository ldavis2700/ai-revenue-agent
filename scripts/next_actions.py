#!/usr/bin/env python3
"""Produce the next safe revenue actions from persisted lead/event state."""
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
FOLLOWUP_HOURS = int(os.getenv('FOLLOWUP_HOURS', '72'))
MAX_FOLLOWUPS = int(os.getenv('MAX_FOLLOWUPS', '2'))


def parse_ts(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)
    actions = []
    leads = conn.execute('SELECT * FROM leads WHERE contact_allowed=1').fetchall()

    for lead in leads:
        events = conn.execute('SELECT event_type, created_at FROM events WHERE lead_id=? ORDER BY created_at', (lead['id'],)).fetchall()
        kinds = [e['event_type'] for e in events]
        if 'opt_out' in kinds or 'sale' in kinds or 'refund' in kinds:
            continue
        if 'interested' in kinds:
            actions.append({'lead_id': lead['id'], 'action': 'human_close', 'reason': 'prospect expressed interest', 'company': lead['company']})
            continue
        if 'reply' in kinds:
            actions.append({'lead_id': lead['id'], 'action': 'review_reply', 'reason': 'prospect replied', 'company': lead['company']})
            continue
        sent_events = [e for e in events if e['event_type'] in {'sent', 'followup_sent'}]
        if not sent_events:
            actions.append({'lead_id': lead['id'], 'action': 'send_initial', 'subject': lead['outreach_subject'], 'body': lead['outreach_body'], 'email': lead['email'], 'company': lead['company']})
            continue
        followups = sum(1 for e in events if e['event_type'] == 'followup_sent')
        last_sent = parse_ts(sent_events[-1]['created_at'])
        if followups < MAX_FOLLOWUPS and now - last_sent >= timedelta(hours=FOLLOWUP_HOURS):
            actions.append({
                'lead_id': lead['id'], 'action': 'send_followup', 'email': lead['email'], 'company': lead['company'],
                'subject': f"Following up: {lead['outreach_subject']}",
                'body': "Hi — just following up on my note. If improving inquiry response and follow-up is useful for your business, I can show you the exact $100 setup before you decide. If not, no problem and I won't keep bothering you."
            })

    print(json.dumps({'generated_at': now.isoformat(), 'actions': actions, 'count': len(actions)}))


if __name__ == '__main__':
    main()
