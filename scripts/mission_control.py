#!/usr/bin/env python3
"""Create one auditable, safety-gated operating plan for AI Revenue Agent."""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
KILL_SWITCH = os.getenv('REVENUE_AGENT_KILL_SWITCH', 'false').lower() == 'true'
EXECUTION_ENABLED = os.getenv('REVENUE_AGENT_EXECUTION_ENABLED', 'false').lower() == 'true'
DAILY_RUN_CAP = max(0, int(os.getenv('REVENUE_AGENT_DAILY_RUN_CAP', '0')))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect(path=DB_PATH):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS agent_mission_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_day TEXT, mode TEXT,
        objective_score REAL, plan TEXT, created_at TEXT
    )''')
    return conn


def scalar(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchone()[0] or 0
    except sqlite3.OperationalError:
        return 0


def snapshot(conn):
    sent = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='sent'")
    replies = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='reply'")
    interested = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='interested'")
    sales = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='sale'")
    gross = scalar(conn, "SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='sale'")
    refunds = scalar(conn, "SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='refund'")
    eligible = scalar(conn, "SELECT COUNT(*) FROM leads WHERE contact_allowed=1 AND score >= ?",
                      (int(os.getenv('MIN_LEAD_SCORE', '55')),))
    return {
        'eligible_leads': eligible, 'sent': sent, 'replies': replies,
        'interested': interested, 'sales': sales,
        'verified_gross_revenue': gross, 'refunds': refunds,
        'verified_net_revenue': gross - refunds,
    }


def objective_score(metrics):
    """Reward verified economics and conversion; never reward raw message volume."""
    sent = max(metrics['sent'], 1)
    return round(
        metrics['verified_net_revenue']
        + (metrics['interested'] / sent) * 25
        + (metrics['sales'] / sent) * 50
        - metrics['refunds'], 2)


def build_plan(metrics):
    plan = []
    if metrics['eligible_leads'] == 0:
        plan.append({'priority': 1, 'action': 'connect_approved_lead_source', 'mode': 'prepare',
                     'reason': 'No qualified, contact-permitted prospects are available.'})
    elif metrics['sent'] == 0:
        plan.append({'priority': 1, 'action': 'prepare_initial_outreach_batch', 'mode': 'prepare',
                     'reason': 'Qualified prospects exist but no delivery is recorded.'})
    elif metrics['replies'] == 0:
        plan.append({'priority': 1, 'action': 'improve_targeting_and_offer_copy', 'mode': 'analyze',
                     'reason': 'Outreach exists but has no recorded replies.'})
    elif metrics['interested'] == 0:
        plan.append({'priority': 1, 'action': 'analyze_reply_objections', 'mode': 'analyze',
                     'reason': 'Replies are not becoming qualified interest.'})
    elif metrics['sales'] == 0:
        plan.append({'priority': 1, 'action': 'prepare_close_and_demo_assets', 'mode': 'prepare',
                     'reason': 'Interest exists but no verified sale is recorded.'})
    else:
        plan.append({'priority': 1, 'action': 'replicate_verified_winning_segment', 'mode': 'analyze',
                     'reason': 'At least one verified sale identifies a segment worth testing.'})
    plan.append({'priority': 2, 'action': 'generate_funnel_report', 'mode': 'execute_internal',
                 'reason': 'Keep every decision tied to measured outcomes.'})
    return plan


def run(path=DB_PATH):
    conn = connect(path)
    today = datetime.now(timezone.utc).date().isoformat()
    used = scalar(conn, 'SELECT COUNT(*) FROM agent_mission_runs WHERE run_day=?', (today,))
    allowed = not KILL_SWITCH and EXECUTION_ENABLED and DAILY_RUN_CAP > used
    metrics = snapshot(conn)
    plan = build_plan(metrics)
    mode = 'execution_authorized' if allowed else 'analysis_and_preparation_only'
    result = {
        'generated_at': now_iso(),
        'mission': 'Maximize sustainable, verified owner revenue while protecting trust and compliance.',
        'mode': mode,
        'execution_gate': {
            'kill_switch': KILL_SWITCH, 'execution_enabled': EXECUTION_ENABLED,
            'daily_run_cap': DAILY_RUN_CAP, 'runs_used_today': used,
            'external_actions_allowed': allowed,
            'spending_allowed': False, 'automatic_charging_allowed': False,
        },
        'metrics': metrics,
        'objective_score': objective_score(metrics),
        'plan': plan,
        'approval_required_for': ['outbound_send', 'spending', 'contracts', 'automatic_charge',
                                  'customer_system_change', 'irreversible_production_change'],
    }
    conn.execute('INSERT INTO agent_mission_runs (run_day,mode,objective_score,plan,created_at) VALUES (?,?,?,?,?)',
                 (today, mode, result['objective_score'], json.dumps(plan), result['generated_at']))
    conn.commit()
    return result


if __name__ == '__main__':
    print(json.dumps(run()))
