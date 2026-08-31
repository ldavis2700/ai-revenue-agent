#!/usr/bin/env python3
"""Create one auditable, safety-gated operating plan for AI Revenue Agent."""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from business_model_intelligence import load_catalog, pursuit_plan, rank_models

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
    conn.execute('''CREATE TABLE IF NOT EXISTS business_model_evidence (
        model_id TEXT PRIMARY KEY,
        observed_revenue REAL NOT NULL DEFAULT 0,
        observed_cost REAL NOT NULL DEFAULT 0,
        conversion_rate REAL NOT NULL DEFAULT 0,
        evidence_quality REAL NOT NULL DEFAULT 0,
        sample_size REAL,
        observed_at TEXT,
        updated_at TEXT NOT NULL
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


def load_persisted_evidence(conn):
    rows = conn.execute('SELECT * FROM business_model_evidence').fetchall()
    evidence = {}
    for row in rows:
        item = {
            'observed_revenue': row['observed_revenue'],
            'observed_cost': row['observed_cost'],
            'conversion_rate': row['conversion_rate'],
            'evidence_quality': row['evidence_quality'],
        }
        if row['sample_size'] is not None:
            item['sample_size'] = row['sample_size']
        if row['observed_at']:
            item['observed_at'] = row['observed_at']
        evidence[row['model_id']] = item
    return evidence


def upsert_business_model_evidence(conn, model_id, observed_revenue=0, observed_cost=0,
                                   conversion_rate=0, evidence_quality=0, sample_size=None,
                                   observed_at=None):
    """Persist measured economics for future Mission Control runs."""
    observed_at = observed_at or now_iso()
    updated_at = now_iso()
    conn.execute('''INSERT INTO business_model_evidence
        (model_id, observed_revenue, observed_cost, conversion_rate, evidence_quality,
         sample_size, observed_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(model_id) DO UPDATE SET
          observed_revenue=excluded.observed_revenue,
          observed_cost=excluded.observed_cost,
          conversion_rate=excluded.conversion_rate,
          evidence_quality=excluded.evidence_quality,
          sample_size=excluded.sample_size,
          observed_at=excluded.observed_at,
          updated_at=excluded.updated_at''',
        (model_id, max(0, float(observed_revenue)), max(0, float(observed_cost)),
         min(1, max(0, float(conversion_rate))), min(1, max(0, float(evidence_quality))),
         None if sample_size is None else max(0, float(sample_size)), observed_at, updated_at))
    conn.commit()


def business_model_snapshot(conn=None):
    """Return APEX's current opportunity portfolio without authorizing external action."""
    constraints = {
        'max_startup_cost': int(os.getenv('APEX_MAX_STARTUP_COST', '3')),
        'max_owner_effort': int(os.getenv('APEX_MAX_OWNER_EFFORT', '5')),
        'max_compliance_risk': int(os.getenv('APEX_MAX_COMPLIANCE_RISK', '4')),
        'min_speed_to_revenue': int(os.getenv('APEX_MIN_SPEED_TO_REVENUE', '5')),
        'min_automation': int(os.getenv('APEX_MIN_AUTOMATION', '6')),
    }
    evidence = load_persisted_evidence(conn) if conn is not None else {}
    evidence_raw = os.getenv('APEX_BUSINESS_MODEL_EVIDENCE_JSON', '').strip()
    if evidence_raw:
        evidence.update(json.loads(evidence_raw))
    catalog = load_catalog()
    ranked = rank_models(catalog['models'], constraints)
    pursuit = pursuit_plan(
        ranked, evidence, int(os.getenv('APEX_PURSUIT_LIMIT', '3')),
        evidence_half_life_days=float(os.getenv('APEX_EVIDENCE_HALF_LIFE_DAYS', '30')))
    return {
        'catalog_size': len(catalog['models']),
        'constraints': constraints,
        'evidence_models': len(evidence),
        'top_candidates': pursuit['pursue'],
        'mode': pursuit['mode'],
        'objective': pursuit['objective'],
        'standing_directives': pursuit['standing_directives'],
        'execution_gate': 'candidate_only',
    }


def build_plan(metrics, model_intelligence=None):
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
    if model_intelligence and model_intelligence.get('top_candidates'):
        top = model_intelligence['top_candidates'][0]
        plan.append({
            'priority': 3,
            'action': 'validate_top_business_model_candidate',
            'mode': 'analyze',
            'candidate_id': top['id'],
            'candidate_name': top['name'],
            'pursuit_score': top['pursuit_score'],
            'experiment_state': top.get('experiment_state', 'validate'),
            'reason': 'Continuously compare current operations against higher-potential legitimate business models.',
        })
    return plan


def run(path=DB_PATH):
    conn = connect(path)
    today = datetime.now(timezone.utc).date().isoformat()
    used = scalar(conn, 'SELECT COUNT(*) FROM agent_mission_runs WHERE run_day=?', (today,))
    allowed = not KILL_SWITCH and EXECUTION_ENABLED and DAILY_RUN_CAP > used
    metrics = snapshot(conn)
    model_intelligence = business_model_snapshot(conn)
    plan = build_plan(metrics, model_intelligence)
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
        'business_model_intelligence': model_intelligence,
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
