#!/usr/bin/env python3
"""Create one auditable, safety-gated operating plan for AI Revenue Agent."""
import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from business_model_intelligence import load_catalog, pursuit_plan, rank_models
from portfolio_competition import compare_candidates
import experiment_queue

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')
KILL_SWITCH = os.getenv('REVENUE_AGENT_KILL_SWITCH', 'false').lower() == 'true'
EXECUTION_ENABLED = os.getenv('REVENUE_AGENT_EXECUTION_ENABLED', 'false').lower() == 'true'
DAILY_RUN_CAP = max(0, int(os.getenv('REVENUE_AGENT_DAILY_RUN_CAP', '0')))

OFFER_FAMILY_MODEL_MAP = {
    'lead_intake_qualification_routing_booking': 'local_business_ai_package',
    'missed_lead_recovery_reactivation': 'lead_generation',
    'crm_sales_ops_automation': 'crm_automation_service',
    'support_resolution_routing': 'ai_customer_support_service',
    'back_office_document_data_workflows': 'document_automation_service',
    'multi_system_operational_integration': 'ai_agent_implementation',
}
MASTERY_ORDER = {
    'learned': 0,
    'paid_validated': 1,
    'repeatable_positive_margin': 2,
    'scale_candidate': 3,
    'productize_candidate': 4,
}
LEDGER_EVIDENCE_KEYS = {
    '_ledger_verified', 'verified_retention_receipts',
    'verified_expansion_receipts', 'retained_recurring_value_cents',
    'expanded_value_delta_cents', 'realized_recurring_net_cents',
    'realized_recurring_contribution_cents', 'realized_recurring_cost_cents',
    'mastery', 'receipt_lineage', 'verified_reuse_receipts',
    'verified_reused_opportunities', 'reuse_receipt_lineage',
}


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
    claimed_sales = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='sale'")
    claimed_sale_value = scalar(conn, "SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='sale'")
    claimed_refund_value = scalar(conn, "SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='refund'")
    collected_payments = scalar(conn, "SELECT COUNT(*) FROM payment_receipts")
    recurring_payments = scalar(
        conn, "SELECT COUNT(*) FROM recurring_payment_receipts")
    one_time_gross = scalar(
        conn, "SELECT COALESCE(SUM(gross_amount_cents),0) / 100.0 FROM payment_receipts")
    one_time_fees = scalar(
        conn, "SELECT COALESCE(SUM(fee_amount_cents),0) / 100.0 FROM payment_receipts")
    one_time_net = scalar(
        conn, "SELECT COALESCE(SUM(net_amount_cents),0) / 100.0 FROM payment_receipts")
    recurring_gross = scalar(
        conn, """SELECT COALESCE(SUM(gross_amount_cents),0) / 100.0
                 FROM recurring_payment_receipts""")
    recurring_fees = scalar(
        conn, """SELECT COALESCE(SUM(fee_amount_cents),0) / 100.0
                 FROM recurring_payment_receipts""")
    recurring_net = scalar(
        conn, """SELECT COALESCE(SUM(net_amount_cents),0) / 100.0
                 FROM recurring_payment_receipts""")
    recurring_withdrawable = scalar(
        conn, """SELECT COALESCE(SUM(amount_cents),0) / 100.0
                 FROM recurring_payout_availability_receipts""")
    recurring_bank_received = scalar(
        conn, """SELECT COALESCE(SUM(amount_cents),0) / 100.0
                 FROM recurring_bank_receipts""")
    opportunity_gross = one_time_gross + recurring_gross
    opportunity_fees = one_time_fees + recurring_fees
    opportunity_net = one_time_net + recurring_net
    eligible = scalar(conn, "SELECT COUNT(*) FROM leads WHERE contact_allowed=1 AND score >= ?",
                      (int(os.getenv('MIN_LEAD_SCORE', '55')),))
    return {
        'eligible_leads': eligible, 'sent': sent, 'replies': replies,
        'interested': interested,
        'sales': collected_payments + recurring_payments,
        'claimed_sale_events': claimed_sales,
        'claimed_sale_value': claimed_sale_value,
        'claimed_refund_value': claimed_refund_value,
        'claimed_sale_status': 'unverified_not_collected_revenue',
        'verified_collected_payments':
            collected_payments + recurring_payments,
        'verified_one_time_payment_receipts': collected_payments,
        'verified_recurring_payment_receipts': recurring_payments,
        'verified_recurring_gross_revenue': recurring_gross,
        'verified_recurring_fees': recurring_fees,
        'verified_recurring_net_revenue': recurring_net,
        'verified_recurring_withdrawable_balance': recurring_withdrawable,
        'verified_recurring_money_received': recurring_bank_received,
        'verified_opportunity_gross_revenue': opportunity_gross,
        'verified_opportunity_fees': opportunity_fees,
        'verified_opportunity_net_revenue': opportunity_net,
        'verified_gross_revenue': opportunity_gross,
        'verified_net_revenue': opportunity_net,
    }


def objective_score(metrics):
    """Reward verified economics and conversion; never reward raw message volume."""
    sent = max(metrics['sent'], 1)
    return round(
        metrics['verified_net_revenue']
        + (metrics['interested'] / sent) * 25
        + (metrics['sales'] / sent) * 50, 2)


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


def ledger_business_model_evidence(conn):
    """Derive model evidence only from verified recurring ledger lineage."""
    try:
        rows = conn.execute('''
            SELECT g.receipt_id AS growth_receipt_id, g.opportunity_id,
                   g.recurring_payment_receipt_id, g.recurring_economics_id,
                   g.kind, g.prior_recurring_payment_receipt_id,
                   g.baseline_value_cents, g.expanded_value_cents,
                   g.occurred_at, o.payload_json,
                   p.net_amount_cents, e.contribution_cents,
                   (e.delivery_cost_cents + e.inference_cost_cents + e.cac_cents)
                     AS realized_cost_cents,
                   (SELECT a.maturity FROM reusable_ip_assets a
                    WHERE a.opportunity_id=g.opportunity_id
                    ORDER BY CASE a.maturity
                      WHEN 'productize_candidate' THEN 4
                      WHEN 'scale_candidate' THEN 3
                      WHEN 'repeatable_positive_margin' THEN 2
                      WHEN 'paid_validated' THEN 1
                      ELSE 0 END DESC LIMIT 1) AS mastery
            FROM recurring_growth_evidence_receipts g
            JOIN opportunities o ON o.id=g.opportunity_id
            JOIN recurring_payment_receipts p
              ON p.receipt_id=g.recurring_payment_receipt_id
            JOIN recurring_realized_unit_economics e
              ON e.economics_id=g.recurring_economics_id
             AND e.recurring_payment_receipt_id=p.receipt_id
            ORDER BY g.occurred_at, g.receipt_id
        ''').fetchall()
    except sqlite3.OperationalError:
        return {}

    aggregated = {}
    for row in rows:
        try:
            payload = json.loads(row['payload_json'])
        except (TypeError, ValueError):
            continue
        family_id = payload.get('offer_family')
        model_id = OFFER_FAMILY_MODEL_MAP.get(family_id)
        if not model_id or row['contribution_cents'] <= 0:
            continue
        item = aggregated.setdefault(model_id, {
            '_ledger_verified': True,
            'verified_retention_receipts': 0,
            'verified_expansion_receipts': 0,
            'retained_recurring_value_cents': 0,
            'expanded_value_delta_cents': 0,
            'realized_recurring_net_cents': 0,
            'realized_recurring_contribution_cents': 0,
            'realized_recurring_cost_cents': 0,
            'mastery': 'learned',
            'receipt_lineage': [],
            'verified_reuse_receipts': 0,
            'verified_reused_opportunities': 0,
            'reuse_receipt_lineage': [],
            '_counted_payments': set(),
            '_reused_opportunities': set(),
        })
        payment_id = row['recurring_payment_receipt_id']
        if payment_id not in item['_counted_payments']:
            item['_counted_payments'].add(payment_id)
            item['realized_recurring_net_cents'] += row['net_amount_cents']
            item['realized_recurring_contribution_cents'] += row['contribution_cents']
            item['realized_recurring_cost_cents'] += row['realized_cost_cents']
        if row['kind'] == 'retention':
            item['verified_retention_receipts'] += 1
            item['retained_recurring_value_cents'] += row['net_amount_cents']
        else:
            item['verified_expansion_receipts'] += 1
            item['expanded_value_delta_cents'] += max(
                0, (row['expanded_value_cents'] or 0)
                - (row['baseline_value_cents'] or 0))
        maturity = row['mastery'] or 'learned'
        if MASTERY_ORDER.get(maturity, 0) > MASTERY_ORDER[item['mastery']]:
            item['mastery'] = maturity
        item['receipt_lineage'].append({
            'growth_receipt_id': row['growth_receipt_id'],
            'kind': row['kind'],
            'recurring_payment_receipt_id':
                row['recurring_payment_receipt_id'],
            'recurring_economics_id': row['recurring_economics_id'],
            'prior_recurring_payment_receipt_id':
                row['prior_recurring_payment_receipt_id'],
            'occurred_at': row['occurred_at'],
        })

    try:
        reuse_rows = conn.execute('''
            SELECT r.receipt_id AS reuse_receipt_id,
                   r.source_opportunity_id, r.reused_opportunity_id,
                   r.economics_kind, r.economics_id, r.occurred_at,
                   source_o.payload_json, source_a.maturity,
                   CASE r.economics_kind
                     WHEN 'one_time' THEN one_e.contribution_cents
                     WHEN 'recurring' THEN recurring_e.contribution_cents
                   END AS contribution_cents
            FROM reusable_ip_reuse_receipts r
            JOIN reusable_ip_assets source_a
              ON source_a.asset_id=r.source_asset_id
             AND source_a.opportunity_id=r.source_opportunity_id
            JOIN reusable_ip_assets reused_a
              ON reused_a.asset_id=r.reused_asset_id
             AND reused_a.opportunity_id=r.reused_opportunity_id
             AND lower(reused_a.name)=lower(source_a.name)
             AND reused_a.asset_type=source_a.asset_type
            JOIN opportunities source_o
              ON source_o.id=r.source_opportunity_id
            LEFT JOIN realized_unit_economics one_e
              ON r.economics_kind='one_time'
             AND one_e.economics_id=r.economics_id
             AND one_e.opportunity_id=r.reused_opportunity_id
            LEFT JOIN recurring_realized_unit_economics recurring_e
              ON r.economics_kind='recurring'
             AND recurring_e.economics_id=r.economics_id
             AND recurring_e.opportunity_id=r.reused_opportunity_id
            WHERE r.source_opportunity_id<>r.reused_opportunity_id
              AND ((r.economics_kind='one_time'
                    AND one_e.contribution_cents>0)
                OR (r.economics_kind='recurring'
                    AND recurring_e.contribution_cents>0))
            ORDER BY r.occurred_at, r.receipt_id
        ''').fetchall()
    except sqlite3.OperationalError:
        reuse_rows = []

    for row in reuse_rows:
        try:
            payload = json.loads(row['payload_json'])
        except (TypeError, ValueError):
            continue
        model_id = OFFER_FAMILY_MODEL_MAP.get(payload.get('offer_family'))
        if not model_id:
            continue
        item = aggregated.setdefault(model_id, {
            '_ledger_verified': True,
            'verified_retention_receipts': 0,
            'verified_expansion_receipts': 0,
            'retained_recurring_value_cents': 0,
            'expanded_value_delta_cents': 0,
            'realized_recurring_net_cents': 0,
            'realized_recurring_contribution_cents': 0,
            'realized_recurring_cost_cents': 0,
            'mastery': 'learned',
            'receipt_lineage': [],
            'verified_reuse_receipts': 0,
            'verified_reused_opportunities': 0,
            'reuse_receipt_lineage': [],
            '_counted_payments': set(),
            '_reused_opportunities': set(),
        })
        item['verified_reuse_receipts'] += 1
        item['_reused_opportunities'].add(row['reused_opportunity_id'])
        maturity = row['maturity'] or 'learned'
        if MASTERY_ORDER.get(maturity, 0) > MASTERY_ORDER[item['mastery']]:
            item['mastery'] = maturity
        item['reuse_receipt_lineage'].append({
            'reuse_receipt_id': row['reuse_receipt_id'],
            'source_opportunity_id': row['source_opportunity_id'],
            'reused_opportunity_id': row['reused_opportunity_id'],
            'economics_kind': row['economics_kind'],
            'economics_id': row['economics_id'],
            'occurred_at': row['occurred_at'],
        })

    for item in aggregated.values():
        payment_sample = len(item.pop('_counted_payments'))
        reused_opportunities = len(item.pop('_reused_opportunities'))
        item['verified_reused_opportunities'] = reused_opportunities
        sample_size = max(payment_sample, reused_opportunities)
        retained = item['verified_retention_receipts']
        timestamps = [
            line['occurred_at'] for line in item['receipt_lineage']]
        timestamps.extend(
            line['occurred_at'] for line in item['reuse_receipt_lineage'])
        item.update({
            'observed_revenue':
                item['realized_recurring_net_cents'] / 100.0,
            'observed_cost':
                item['realized_recurring_cost_cents'] / 100.0,
            'conversion_rate': min(1.0, retained / max(sample_size, 1)),
            'evidence_quality': 1.0,
            'sample_size': sample_size,
            'observed_at': max(timestamps),
        })
    return aggregated


def _finite_evidence_value(value, field):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{field} must be finite')
    return number


def upsert_business_model_evidence(conn, model_id, observed_revenue=0, observed_cost=0,
                                   conversion_rate=0, evidence_quality=0, sample_size=None,
                                   observed_at=None, *, commit=True):
    """Persist measured economics for future Mission Control runs."""
    # Validate before clamping: min/max can conceal NaN or infinity as a
    # plausible measurement. No invalid insert may overwrite prior evidence.
    revenue = max(0, _finite_evidence_value(observed_revenue, 'observed_revenue'))
    cost = max(0, _finite_evidence_value(observed_cost, 'observed_cost'))
    conversion = min(1, max(0, _finite_evidence_value(conversion_rate, 'conversion_rate')))
    quality = min(1, max(0, _finite_evidence_value(evidence_quality, 'evidence_quality')))
    samples = None if sample_size is None else max(0, _finite_evidence_value(sample_size, 'sample_size'))
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
        (model_id, revenue, cost, conversion, quality, samples, observed_at, updated_at))
    if commit:
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
    # Ledger-only maturity fields cannot be asserted through environment or
    # manually persisted evidence. Verified ledger lineage overwrites the
    # ranking inputs for any model it proves.
    for item in evidence.values():
        if isinstance(item, dict):
            for key in LEDGER_EVIDENCE_KEYS:
                item.pop(key, None)
    ledger_evidence = (
        ledger_business_model_evidence(conn) if conn is not None else {})
    evidence.update(ledger_evidence)
    catalog = load_catalog()
    ranked = rank_models(catalog['models'], constraints)
    pursuit = pursuit_plan(
        ranked, evidence, int(os.getenv('APEX_PURSUIT_LIMIT', '3')),
        evidence_half_life_days=float(os.getenv('APEX_EVIDENCE_HALF_LIFE_DAYS', '30')))
    competition = compare_candidates(pursuit['pursue'])
    return {
        'catalog_size': len(catalog['models']),
        'constraints': constraints,
        'evidence_models': len(evidence),
        'ledger_verified_evidence_models': len(ledger_evidence),
        'verified_model_evidence': ledger_evidence,
        'top_candidates': pursuit['pursue'],
        'portfolio_competition': competition,
        'mode': pursuit['mode'],
        'objective': pursuit['objective'],
        'standing_directives': pursuit['standing_directives'],
        'execution_gate': 'candidate_only',
    }


def ensure_zero_cost_validation(path, model_intelligence):
    """Ensure one bounded zero-spend experiment exists for the best current challenger/candidate."""
    competition = (model_intelligence or {}).get('portfolio_competition') or {}
    candidate = competition.get('challenger')
    if not candidate:
        candidates = (model_intelligence or {}).get('top_candidates') or []
        candidate = candidates[0] if candidates else None

    qconn = experiment_queue.connect(path)
    try:
        if not candidate or candidate.get('experiment_state') == 'deprioritize':
            return {
                'candidate_id': None,
                'experiment': None,
                'queue': experiment_queue.queue_summary(qconn),
                'execution_gate': 'recommendation_only',
            }

        target = min(1.0, max(0.0, float(os.getenv('APEX_ZERO_COST_VALIDATION_TARGET', '0.05'))))
        max_samples = max(1.0, float(os.getenv('APEX_ZERO_COST_VALIDATION_MAX_SAMPLES', '20')))
        model_id = candidate['id']
        model_name = candidate.get('name', model_id)
        queued = experiment_queue.enqueue_experiment(
            qconn,
            model_id=model_id,
            hypothesis=f'{model_name} can produce measurable demand without paid acquisition.',
            success_metric='conversion_rate',
            target_value=target,
            priority=10 if competition.get('challenger') else 20,
            max_cost=0,
            max_samples=max_samples,
        )
        return {
            'candidate_id': model_id,
            'experiment': queued,
            'queue': experiment_queue.queue_summary(qconn),
            'execution_gate': 'recommendation_only',
        }
    finally:
        qconn.close()


def build_plan(metrics, model_intelligence=None, validation_queue=None):
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
    if model_intelligence:
        competition = model_intelligence.get('portfolio_competition') or {}
        if competition.get('recommended_action'):
            champion = competition.get('champion') or {}
            challenger = competition.get('challenger') or {}
            plan.append({
                'priority': 3,
                'action': 'evaluate_portfolio_competition',
                'mode': 'analyze',
                'posture': competition.get('posture'),
                'recommended_action': competition.get('recommended_action'),
                'champion_id': champion.get('id'),
                'challenger_id': challenger.get('id'),
                'reason': 'Protect measured winners while continuously probing credible alternatives.',
            })
    if model_intelligence and model_intelligence.get('top_candidates'):
        top = model_intelligence['top_candidates'][0]
        plan.append({
            'priority': 4,
            'action': 'validate_top_business_model_candidate',
            'mode': 'analyze',
            'candidate_id': top['id'],
            'candidate_name': top['name'],
            'pursuit_score': top['pursuit_score'],
            'experiment_state': top.get('experiment_state', 'validate'),
            'reason': 'Continuously compare current operations against higher-potential legitimate business models.',
        })
    if validation_queue and validation_queue.get('experiment'):
        experiment = validation_queue['experiment']
        plan.append({
            'priority': 5,
            'action': 'prepare_next_zero_cost_validation',
            'mode': 'prepare',
            'candidate_id': validation_queue.get('candidate_id'),
            'experiment_id': experiment.get('id'),
            'experiment_status': experiment.get('status'),
            'max_cost': experiment.get('max_cost'),
            'max_samples': experiment.get('max_samples'),
            'reason': 'Turn portfolio intelligence into a bounded, measurable zero-spend validation queue.',
        })
    return plan


def run(path=DB_PATH):
    conn = connect(path)
    today = datetime.now(timezone.utc).date().isoformat()
    used = scalar(conn, 'SELECT COUNT(*) FROM agent_mission_runs WHERE run_day=?', (today,))
    allowed = not KILL_SWITCH and EXECUTION_ENABLED and DAILY_RUN_CAP > used
    metrics = snapshot(conn)
    model_intelligence = business_model_snapshot(conn)
    validation_queue = ensure_zero_cost_validation(path, model_intelligence)
    plan = build_plan(metrics, model_intelligence, validation_queue)
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
        'zero_cost_validation_queue': validation_queue,
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
