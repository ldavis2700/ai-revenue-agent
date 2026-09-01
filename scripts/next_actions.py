#!/usr/bin/env python3
"""Produce the next safe revenue actions from persisted lead/event state."""
import json
import os
import sqlite3
import urllib.parse
from datetime import datetime, timezone, timedelta

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
FOLLOWUP_HOURS = int(os.getenv('FOLLOWUP_HOURS', '72'))
MAX_FOLLOWUPS = int(os.getenv('MAX_FOLLOWUPS', '2'))
OFFER_PRICE = os.getenv('OFFER_PRICE', '100')
OFFER_NAME = os.getenv('OFFER_NAME', 'AI Customer Response System')
MANAGED_MONTHLY_PRICE = os.getenv('MANAGED_MONTHLY_PRICE', '99')
CHECKOUT_URL_TEMPLATE = os.getenv('CHECKOUT_URL_TEMPLATE', '').strip()
MANAGED_CHECKOUT_URL_TEMPLATE = os.getenv('MANAGED_CHECKOUT_URL_TEMPLATE', '').strip()


def parse_ts(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def checkout_url(lead, template=CHECKOUT_URL_TEMPLATE, amount=OFFER_PRICE, offer=OFFER_NAME):
    if not template:
        return None
    values = {
        'lead_id': urllib.parse.quote(str(lead['id']), safe=''),
        'email': urllib.parse.quote(str(lead['email'] or ''), safe=''),
        'amount': urllib.parse.quote(str(amount), safe=''),
        'offer': urllib.parse.quote(str(offer), safe=''),
    }
    return template.format(**values)


def reply_state(kinds):
    """Return the safest next reply state from explicit persisted evidence.

    A generic reply or legacy interest signal remains owner-review only.
    Autonomous closing may advance only when an upstream authenticated classifier
    or operator has persisted the explicit affirmative_purchase_intent event.
    This prevents ambiguous interest from being treated as consent to buy.
    """
    if 'affirmative_purchase_intent' in kinds:
        return 'interested'
    if 'reply' in kinds or 'interested' in kinds:
        return 'review_reply'
    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)
    actions = []
    leads = conn.execute('SELECT * FROM leads WHERE contact_allowed=1').fetchall()

    for lead in leads:
        events = conn.execute('SELECT event_type, created_at FROM events WHERE lead_id=? ORDER BY created_at', (lead['id'],)).fetchall()
        kinds = [e['event_type'] for e in events]
        if 'opt_out' in kinds or 'refund' in kinds:
            continue
        if 'managed_plan_active' in kinds:
            continue
        if 'managed_plan_interested' in kinds:
            if 'managed_checkout_sent' in kinds:
                continue
            managed_offer = f'{OFFER_NAME} Managed Plan'
            url = checkout_url(lead, MANAGED_CHECKOUT_URL_TEMPLATE, MANAGED_MONTHLY_PRICE, managed_offer)
            actions.append({
                'lead_id': lead['id'],
                'action': 'send_managed_checkout' if url else 'human_close_managed',
                'reason': 'customer affirmatively expressed interest in optional managed plan',
                'company': lead['company'],
                'email': lead['email'],
                'checkout_url': url,
                'amount': float(MANAGED_MONTHLY_PRICE),
                'billing': 'monthly',
                'offer': managed_offer,
            })
            continue
        if 'sale' in kinds:
            actions.append({
                'lead_id': lead['id'],
                'action': 'offer_optional_managed_plan',
                'reason': 'verified setup customer is eligible for optional ongoing optimization',
                'company': lead['company'],
                'email': lead['email'],
                'amount': float(MANAGED_MONTHLY_PRICE),
                'billing': 'monthly',
                'body': (
                    f'Your {OFFER_NAME} setup is complete. If you want ongoing response and follow-up optimization, '
                    f'I also offer an optional managed plan at ${MANAGED_MONTHLY_PRICE}/month. '
                    'Nothing changes unless you choose to enroll.'
                ),
            })
            continue
        reply = reply_state(kinds)
        if reply == 'interested':
            if 'checkout_sent' in kinds:
                continue
            url = checkout_url(lead)
            actions.append({
                'lead_id': lead['id'],
                'action': 'send_checkout' if url else 'human_close',
                'reason': 'prospect has explicit persisted affirmative purchase intent',
                'company': lead['company'],
                'email': lead['email'],
                'checkout_url': url,
                'amount': float(OFFER_PRICE),
                'offer': OFFER_NAME,
            })
            continue
        if reply == 'review_reply':
            actions.append({'lead_id': lead['id'], 'action': 'review_reply', 'reason': 'prospect replied or expressed interest but purchase intent is not explicit', 'company': lead['company']})
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
