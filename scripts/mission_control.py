#!/usr/bin/env python3
"""Create one auditable, safety-gated operating plan for AI Revenue Agent."""
import json
import hashlib
import math
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from business_model_intelligence import load_catalog, pursuit_plan, rank_models
from portfolio_competition import compare_candidates
from opportunity_intake import (
    PIPELINE_EVIDENCE_PREFIXES,
    _verified_realized_economics,
    _verified_recurring_growth_evidence,
    _verified_reusable_ip_maturity,
    _verified_reusable_ip_reuse_evidence,
)
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
    'verified_forecast_comparisons', 'forecast_mean_absolute_error_cents',
    'forecast_mean_projected_contribution_cents',
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


RECEIPT_SPECS = {
    'payment_receipts': (
        'payr_',
        ('opportunity_id', 'invoice_receipt_id', 'provider',
         'external_transaction_id', 'transaction_url', 'gross_amount_cents',
         'fee_amount_cents', 'net_amount_cents', 'currency', 'paid_at',
         'settled_at'),
    ),
    'recurring_payment_receipts': (
        'recurpay_',
        ('opportunity_id', 'contract_receipt_id', 'term_id', 'provider',
         'external_invoice_id', 'invoice_url', 'external_transaction_id',
         'transaction_url', 'gross_amount_cents', 'fee_amount_cents',
         'net_amount_cents', 'currency', 'service_period_start',
         'service_period_end', 'invoiced_at', 'paid_at', 'settled_at'),
    ),
    'payout_availability_receipts': (
        'pavr_',
        ('opportunity_id', 'payment_receipt_id', 'provider',
         'external_balance_id', 'evidence_url', 'amount_cents', 'currency',
         'available_at'),
    ),
    'recurring_payout_availability_receipts': (
        'recuravail_',
        ('opportunity_id', 'recurring_payment_receipt_id', 'provider',
         'external_balance_id', 'evidence_url', 'amount_cents', 'currency',
         'available_at'),
    ),
    'bank_receipts': (
        'bankr_',
        ('opportunity_id', 'payout_availability_receipt_id',
         'financial_institution', 'external_transfer_id', 'evidence_url',
         'amount_cents', 'currency', 'received_at'),
    ),
    'recurring_bank_receipts': (
        'recurbank_',
        ('opportunity_id', 'recurring_payout_receipt_id',
         'financial_institution', 'external_transfer_id', 'evidence_url',
         'amount_cents', 'currency', 'received_at'),
    ),
}


def verified_receipt_rows(conn, table):
    """Return only hash-consistent rows from a production receipt table.

    Unsealed legacy rows are not discarded from storage, but they are never
    promoted into metrics labeled verified. Only immutable receipt schemas can
    contribute to collected, withdrawable, or received totals.
    """
    try:
        columns = {
            row[1] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()
        }
    except sqlite3.OperationalError:
        return []
    if not columns:
        return []
    prefix, snapshot_columns = RECEIPT_SPECS[table]
    if 'receipt_hash' not in columns:
        return []
    required = {'receipt_id', 'receipt_hash', *snapshot_columns}
    if not required.issubset(columns):
        return []
    selected = ('receipt_id', *snapshot_columns, 'receipt_hash')
    rows = conn.execute(
        f"SELECT {','.join(selected)} FROM {table}"
    ).fetchall()
    verified = []
    for row in rows:
        item = dict(zip(selected, row))
        snapshot = {key: item[key] for key in snapshot_columns}
        serialized = json.dumps(snapshot, sort_keys=True, separators=(',', ':'))
        expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
        if (item['receipt_hash'] == expected_hash
                and item['receipt_id'] == prefix + expected_hash[:24]):
            verified.append(item)
    return verified


def receipt_totals(conn, table, amount_columns):
    rows = verified_receipt_rows(conn, table)
    return len(rows), {
        column: sum((row.get(column) or 0) for row in rows) / 100.0
        for column in amount_columns
    }


ACTIVE_BUYER_STAGES = (
    'response_received', 'buyer_reply', 'interview', 'offer', 'contracted',
    'executing', 'qa_passed', 'delivered', 'invoiced',
)
BUYER_STAGE_PRIORITY = {
    stage: index for index, stage in enumerate(ACTIVE_BUYER_STAGES, start=1)
}



def _contract_terms_binding(
        conn, table, contract_receipt_id, opportunity_id,
        amount_column, amount_key):
    """Return a verified optional pricing binding used by a contract seal."""
    row = conn.execute(
        f"""SELECT term_id,accepted_terms_hash,{amount_column},
                   acceptance_evidence_url,accepted_at,binding_hash
            FROM {table}
            WHERE contract_receipt_id=? AND opportunity_id=?""",
        (contract_receipt_id, opportunity_id),
    ).fetchone()
    if row is None:
        return None
    binding = {
        'term_id': row[0],
        'accepted_terms_hash': row[1],
        amount_key: row[2],
        'acceptance_evidence_url': row[3],
        'accepted_at': row[4],
    }
    binding_seal = {
        'contract_receipt_id': contract_receipt_id,
        'opportunity_id': opportunity_id,
        **binding,
    }
    expected = hashlib.sha256(json.dumps(
        binding_seal, sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()
    if row[5] != expected:
        return False
    return binding

def _canonical_ledger_id(value, prefix):
    return (
        isinstance(value, str)
        and re.fullmatch(re.escape(prefix) + r'[0-9a-f]{24}', value) is not None
    )


def _verified_submission_artifact(conn, opportunity_id, receipt_id):
    row = conn.execute(
        '''SELECT proposal_id,provider,external_submission_id,
                  submission_url,submitted_at,receipt_hash
           FROM submission_receipts
           WHERE receipt_id=? AND opportunity_id=?''',
        (receipt_id, opportunity_id),
    ).fetchone()
    if row is None:
        return False
    snapshot = {
        'opportunity_id': opportunity_id,
        'proposal_id': row[0],
        'provider': row[1],
        'external_submission_id': row[2],
        'submission_url': row[3],
        'submitted_at': row[4],
    }
    expected = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()
    return (
        row[5] == expected
        and receipt_id == 'subr_' + expected[:24]
    )


def _verified_response_artifact(
        conn, opportunity_id, receipt_id, stage):
    row = conn.execute(
        '''SELECT rr.submission_receipt_id,rr.provider,
                  rr.external_message_id,rr.message_url,rr.received_at,
                  rr.receipt_hash,sr.provider
           FROM response_receipts rr
           JOIN submission_receipts sr
             ON sr.receipt_id=rr.submission_receipt_id
            AND sr.opportunity_id=rr.opportunity_id
           WHERE rr.receipt_id=? AND rr.opportunity_id=?''',
        (receipt_id, opportunity_id),
    ).fetchone()
    if row is None:
        return False
    snapshot = {
        'opportunity_id': opportunity_id,
        'submission_receipt_id': row[0],
        'provider': row[1],
        'external_message_id': row[2],
        'message_url': row[3],
        'received_at': row[4],
        'stage': stage,
    }
    expected = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()
    return (
        _canonical_ledger_id(row[0], 'subr_')
        and row[1] == row[6]
        and row[5] == expected
        and receipt_id == 'respr_' + expected[:24]
        and _verified_submission_artifact(
            conn, opportunity_id, row[0])
    )


def _verified_response_lineage(
        conn, opportunity_id, receipt_id, proposal_id, provider):
    if not _canonical_ledger_id(receipt_id, 'respr_'):
        return False
    proposal = conn.execute(
        '''SELECT sr.proposal_id,sr.provider,rr.provider
           FROM response_receipts rr
           JOIN submission_receipts sr
             ON sr.receipt_id=rr.submission_receipt_id
           WHERE rr.receipt_id=? AND rr.opportunity_id=?
             AND sr.opportunity_id=?''',
        (receipt_id, opportunity_id, opportunity_id),
    ).fetchone()
    if (
        proposal is None
        or proposal[0] != proposal_id
        or proposal[1] != provider
        or proposal[2] != provider
    ):
        return False
    stage_prefixes = (
        ('response_received', 'reply:'),
        ('buyer_reply', 'reply:'),
        ('interview', 'interview:'),
        ('offer', 'offer:'),
    )
    for stage, prefix in stage_prefixes:
        evidence_id = prefix + receipt_id
        row = conn.execute(
            '''SELECT evidence_hash FROM opportunity_transitions
               WHERE opportunity_id=? AND to_state=? AND evidence_id=?''',
            (opportunity_id, stage, evidence_id),
        ).fetchone()
        if (
            row is not None
            and row[0] == hashlib.sha256(evidence_id.encode()).hexdigest()
            and _verified_response_artifact(
                conn, opportunity_id, receipt_id, stage)
        ):
            return True
    return False


def _verified_contract_artifact(conn, opportunity_id, receipt_id):
    row = conn.execute(
        '''SELECT response_receipt_id,proposal_id,provider,
                  external_contract_id,contract_url,amount_cents,
                  currency,contracted_at,terms_authority,
                  authority_evidence_url,receipt_hash
           FROM contract_receipts
           WHERE receipt_id=? AND opportunity_id=?''',
        (receipt_id, opportunity_id),
    ).fetchone()
    if row is None:
        return False
    recurring = _contract_terms_binding(
        conn, 'contract_recurring_terms', receipt_id, opportunity_id,
        'accepted_base_fee_cents', 'accepted_base_fee_cents')
    outcome = _contract_terms_binding(
        conn, 'contract_outcome_terms', receipt_id, opportunity_id,
        'accepted_fee_cap_cents', 'accepted_fee_cap_cents')
    if recurring is False or outcome is False:
        return False
    snapshot = {
        'opportunity_id': opportunity_id,
        'response_receipt_id': row[0],
        'proposal_id': row[1],
        'provider': row[2],
        'external_contract_id': row[3],
        'contract_url': row[4],
        'amount_cents': row[5],
        'currency': row[6],
        'contracted_at': row[7],
        'terms_authority': row[8],
        'authority_evidence_url': row[9],
        'recurring_terms_binding': recurring,
        'outcome_terms_binding': outcome,
    }
    expected = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()
    return (
        _canonical_ledger_id(row[0], 'respr_')
        and row[10] == expected
        and receipt_id == 'contr_' + expected[:24]
        and _verified_response_lineage(
            conn, opportunity_id, row[0], row[1], row[2])
    )


def _verified_execution_artifact(
        conn, opportunity_id, plan_id, contract_receipt_id=None):
    row = conn.execute(
        '''SELECT contract_receipt_id,plan_hash,plan_json,started_at
           FROM execution_plans
           WHERE plan_id=? AND opportunity_id=?''',
        (plan_id, opportunity_id),
    ).fetchone()
    if row is None or (
            contract_receipt_id is not None
            and row[0] != contract_receipt_id):
        return False
    expected = hashlib.sha256(row[2].encode()).hexdigest()
    payload = json.loads(row[2])
    return (
        isinstance(payload, dict)
        and _canonical_ledger_id(row[0], 'contr_')
        and payload.get('opportunity_id') == opportunity_id
        and payload.get('contract_receipt_id') == row[0]
        and payload.get('started_at') == row[3]
        and row[1] == expected
        and plan_id == 'execp_' + expected[:24]
        and _verified_contract_artifact(
            conn, opportunity_id, row[0])
    )


def _verified_qa_artifact(conn, opportunity_id, report_id):
    row = conn.execute(
        '''SELECT report_hash,report_json,execution_plan_id,
                  artifact_sha256,completed_at
           FROM qa_reports
           WHERE report_id=? AND opportunity_id=?''',
        (report_id, opportunity_id),
    ).fetchone()
    if row is None:
        return False
    expected = hashlib.sha256(row[1].encode()).hexdigest()
    payload = json.loads(row[1])
    return (
        isinstance(payload, dict)
        and payload.get('opportunity_id') == opportunity_id
        and payload.get('execution_plan_id') == row[2]
        and _canonical_ledger_id(row[2], 'execp_')
        and payload.get('artifact_sha256') == row[3]
        and payload.get('completed_at') == row[4]
        and row[0] == expected
        and report_id == 'qar_' + expected[:24]
        and _verified_execution_artifact(
            conn, opportunity_id, row[2])
    )


def _verified_delivery_artifact(conn, opportunity_id, receipt_id):
    row = conn.execute(
        '''SELECT qa_report_id,provider,external_delivery_id,
                  delivery_url,artifact_sha256,delivered_at,receipt_hash
           FROM delivery_receipts
           WHERE receipt_id=? AND opportunity_id=?''',
        (receipt_id, opportunity_id),
    ).fetchone()
    if row is None:
        return False
    snapshot = {
        'opportunity_id': opportunity_id,
        'qa_report_id': row[0],
        'provider': row[1],
        'external_delivery_id': row[2],
        'delivery_url': row[3],
        'artifact_sha256': row[4],
        'delivered_at': row[5],
    }
    expected = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()
    return (
        _canonical_ledger_id(row[0], 'qar_')
        and row[6] == expected
        and receipt_id == 'delr_' + expected[:24]
        and _verified_qa_artifact(conn, opportunity_id, row[0])
    )


def _buyer_stage_artifact_exists(conn, opportunity_id, stage, evidence_id):
    """Rebuild or identity-check the stage-specific immutable ledger artifact."""
    evidence_prefixes = {
        'response_received': 'reply:',
        'buyer_reply': 'reply:',
        'interview': 'interview:',
        'offer': 'offer:',
        'contracted': 'contract:',
        'executing': 'contract:',
        'qa_passed': 'qa:',
        'delivered': 'delivery:',
        'invoiced': 'invoice:',
    }
    expected_prefix = evidence_prefixes.get(stage)
    if (not isinstance(evidence_id, str) or expected_prefix is None
            or not evidence_id.startswith(expected_prefix)):
        return False
    try:
        if stage in {'response_received', 'buyer_reply', 'interview', 'offer'}:
            receipt_id = evidence_id.split(':', 1)[1]
            return _verified_response_artifact(
                conn, opportunity_id, receipt_id, stage)
        if stage == 'contracted':
            receipt_id = evidence_id.split(':', 1)[1]
            return _verified_contract_artifact(
                conn, opportunity_id, receipt_id)
        if stage == 'executing':
            parts = evidence_id.split(':')
            if (len(parts) != 4 or parts[2] != 'plan'
                    or not _canonical_ledger_id(parts[1], 'contr_')):
                return False
            return _verified_execution_artifact(
                conn, opportunity_id, parts[3], parts[1])
        receipt_id = evidence_id.split(':', 1)[1]
        if stage == 'qa_passed':
            return _verified_qa_artifact(
                conn, opportunity_id, receipt_id)
        if stage == 'delivered':
            return _verified_delivery_artifact(
                conn, opportunity_id, receipt_id)
        if stage == 'invoiced':
            row = conn.execute(
                '''SELECT delivery_receipt_id,provider,external_invoice_id,
                          invoice_url,amount_cents,currency,issued_at,due_at,
                          receipt_hash
                   FROM invoice_receipts
                   WHERE receipt_id=? AND opportunity_id=?''',
                (receipt_id, opportunity_id),
            ).fetchone()
            if row is None:
                return False
            outcomes = conn.execute(
                '''SELECT ioe.event_id,ioe.outcome_fee_cents,aoe.event_hash
                   FROM invoice_outcome_events ioe
                   JOIN attributed_outcome_events aoe
                     ON aoe.event_id=ioe.event_id
                   WHERE ioe.invoice_receipt_id=?
                   ORDER BY ioe.event_id''',
                (receipt_id,),
            ).fetchall()
            snapshot = {
                'opportunity_id': opportunity_id,
                'delivery_receipt_id': row[0],
                'provider': row[1],
                'external_invoice_id': row[2],
                'invoice_url': row[3],
                'amount_cents': row[4],
                'outcome_fee_cents': sum(item[1] for item in outcomes),
                'outcome_event_ids': [item[0] for item in outcomes],
                'outcome_event_hashes': [
                    {'event_id': item[0], 'event_hash': item[2]}
                    for item in outcomes
                ],
                'currency': row[5],
                'issued_at': row[6],
                'due_at': row[7],
            }
            expected = hashlib.sha256(json.dumps(
                snapshot, sort_keys=True, separators=(',', ':')
            ).encode()).hexdigest()
            return (
                _canonical_ledger_id(row[0], 'delr_')
                and row[8] == expected
                and receipt_id == 'invr_' + expected[:24]
                and _verified_delivery_artifact(
                    conn, opportunity_id, row[0])

            )
        return False
    except (
        AttributeError, IndexError, KeyError, TypeError, ValueError,
        sqlite3.OperationalError,
    ):
        return False

def active_buyer_pipeline(conn):
    """Summarize only receipt-backed, integrity-checked active buyer work."""
    counts = {stage: 0 for stage in ACTIVE_BUYER_STAGES}
    try:
        rows = conn.execute(
            "SELECT o.id,o.pipeline_state,t.evidence_id,t.evidence_hash "
            "FROM opportunities o JOIN opportunity_transitions t "
            "ON t.opportunity_id=o.id AND t.to_state=o.pipeline_state "
            "WHERE o.pipeline_state IN ("
            + ",".join("?" for _ in ACTIVE_BUYER_STAGES)
            + ")",
            ACTIVE_BUYER_STAGES,
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    seen = set()
    for opportunity_id, stage, evidence_id, evidence_hash in rows:
        key = (opportunity_id, stage)
        prefixes = PIPELINE_EVIDENCE_PREFIXES.get(stage, ())
        if (
            key in seen
            or not isinstance(evidence_id, str)
            or not evidence_id.startswith(prefixes)
            or hashlib.sha256(evidence_id.encode()).hexdigest() != evidence_hash
            or not _buyer_stage_artifact_exists(
                conn, opportunity_id, stage, evidence_id
            )
        ):
            continue
        seen.add(key)
        counts[stage] += 1
    highest = max(
        (stage for stage, count in counts.items() if count),
        key=lambda stage: BUYER_STAGE_PRIORITY[stage],
        default=None,
    )
    return {
        'active_count': sum(counts.values()),
        'highest_stage': highest,
        'stage_counts': counts,
    }

def snapshot(conn):
    sent = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='sent'")
    replies = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='reply'")
    interested = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='interested'")
    claimed_sales = scalar(conn, "SELECT COUNT(*) FROM events WHERE event_type='sale'")
    claimed_sale_value = scalar(conn, "SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='sale'")
    claimed_refund_value = scalar(conn, "SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='refund'")
    collected_payments, one_time = receipt_totals(
        conn, 'payment_receipts',
        ('gross_amount_cents', 'fee_amount_cents', 'net_amount_cents'))
    recurring_payments, recurring = receipt_totals(
        conn, 'recurring_payment_receipts',
        ('gross_amount_cents', 'fee_amount_cents', 'net_amount_cents'))
    _, recurring_payout = receipt_totals(
        conn, 'recurring_payout_availability_receipts', ('amount_cents',))
    _, recurring_bank = receipt_totals(
        conn, 'recurring_bank_receipts', ('amount_cents',))
    _, one_time_payout = receipt_totals(
        conn, 'payout_availability_receipts', ('amount_cents',))
    _, one_time_bank = receipt_totals(
        conn, 'bank_receipts', ('amount_cents',))
    one_time_gross = one_time['gross_amount_cents']
    one_time_fees = one_time['fee_amount_cents']
    one_time_net = one_time['net_amount_cents']
    recurring_gross = recurring['gross_amount_cents']
    recurring_fees = recurring['fee_amount_cents']
    recurring_net = recurring['net_amount_cents']
    recurring_withdrawable = recurring_payout['amount_cents']
    recurring_bank_received = recurring_bank['amount_cents']
    one_time_withdrawable = one_time_payout['amount_cents']
    one_time_bank_received = one_time_bank['amount_cents']
    opportunity_gross = one_time_gross + recurring_gross
    opportunity_fees = one_time_fees + recurring_fees
    opportunity_net = one_time_net + recurring_net
    eligible = scalar(conn, "SELECT COUNT(*) FROM leads WHERE contact_allowed=1 AND score >= ?",
                      (int(os.getenv('MIN_LEAD_SCORE', '55')),))
    buyer_pipeline = active_buyer_pipeline(conn)
    return {
        'active_buyer_opportunities': buyer_pipeline['active_count'],
        'highest_active_buyer_stage': buyer_pipeline['highest_stage'],
        'active_buyer_stage_counts': buyer_pipeline['stage_counts'],
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
        'verified_one_time_withdrawable_balance': one_time_withdrawable,
        'verified_one_time_money_received': one_time_bank_received,
        'verified_withdrawable_balance':
            one_time_withdrawable + recurring_withdrawable,
        'verified_money_received':
            one_time_bank_received + recurring_bank_received,
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
                   (SELECT a.asset_id FROM reusable_ip_assets a
                    WHERE a.opportunity_id=g.opportunity_id
                    ORDER BY CASE a.maturity
                      WHEN 'productize_candidate' THEN 4
                      WHEN 'scale_candidate' THEN 3
                      WHEN 'repeatable_positive_margin' THEN 2
                      WHEN 'paid_validated' THEN 1
                      ELSE 0 END DESC LIMIT 1) AS mastery_asset_id,
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
        rows = []

    aggregated = {}
    for row in rows:
        _verified_recurring_growth_evidence(
            conn, row['growth_receipt_id'])
        verified_maturity = 'learned'
        if row['mastery_asset_id']:
            verified_maturity = _verified_reusable_ip_maturity(
                conn, row['mastery_asset_id'])['maturity']
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
        maturity = verified_maturity
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
                   r.source_asset_id, r.source_opportunity_id,
                   r.reused_opportunity_id,
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
        _verified_reusable_ip_reuse_evidence(
            conn, row['reuse_receipt_id'])
        verified_maturity = _verified_reusable_ip_maturity(
            conn, row['source_asset_id'])['maturity']
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
        maturity = verified_maturity
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

    try:
        forecast_ids = [row[0] for row in conn.execute(
            "SELECT economics_id FROM realized_unit_economics "
            "ORDER BY measured_at,economics_id").fetchall()]
    except sqlite3.OperationalError:
        forecast_ids = []
    for economics_id in forecast_ids:
        # Rebuild payment/proposal lineage before any forecast result can alter
        # model priority. A changed receipt or proposal fails the whole snapshot.
        _verified_realized_economics(conn, economics_id)
        row = conn.execute('''
            SELECT e.opportunity_id, e.delivery_cost_cents,
                   e.inference_cost_cents, e.cac_cents, e.measured_at,
                   e.evidence_json, o.payload_json, p.net_amount_cents
            FROM realized_unit_economics e
            JOIN opportunities o ON o.id=e.opportunity_id
            JOIN payment_receipts p
              ON p.receipt_id=e.payment_receipt_id
             AND p.opportunity_id=e.opportunity_id
            WHERE e.economics_id=?
        ''', (economics_id,)).fetchone()
        if row is None:
            raise ValueError('realized_economics_unverified')
        try:
            evidence = json.loads(row['evidence_json'])
            payload = json.loads(row['payload_json'])
        except (TypeError, ValueError) as exc:
            raise ValueError('realized_economics_unverified') from exc
        comparison = evidence.get('proposal_projection_comparison')
        model_id = OFFER_FAMILY_MODEL_MAP.get(payload.get('offer_family'))
        if not isinstance(comparison, dict) or not model_id:
            continue
        projected = comparison.get('projected_contribution_cents')
        variance = comparison.get('contribution_variance_cents')
        if not isinstance(projected, int) or not isinstance(variance, int):
            raise ValueError('realized_economics_unverified')
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
        item.setdefault('_forecast_count', 0)
        item.setdefault('_forecast_projected_total', 0)
        item.setdefault('_forecast_absolute_error_total', 0)
        item.setdefault('_forecast_observed_at', [])
        item.setdefault('_one_time_net_cents', 0)
        item.setdefault('_one_time_cost_cents', 0)
        item['_forecast_count'] += 1
        item['_forecast_projected_total'] += projected
        item['_forecast_absolute_error_total'] += abs(variance)
        item['_forecast_observed_at'].append(row['measured_at'])
        item['_one_time_net_cents'] += row['net_amount_cents']
        item['_one_time_cost_cents'] += (
            row['delivery_cost_cents'] + row['inference_cost_cents']
            + row['cac_cents'])

    for item in aggregated.values():
        payment_sample = len(item.pop('_counted_payments'))
        reused_opportunities = len(item.pop('_reused_opportunities'))
        item['verified_reused_opportunities'] = reused_opportunities
        forecast_count = item.pop('_forecast_count', 0)
        projected_total = item.pop('_forecast_projected_total', 0)
        absolute_error_total = item.pop('_forecast_absolute_error_total', 0)
        forecast_timestamps = item.pop('_forecast_observed_at', [])
        one_time_net = item.pop('_one_time_net_cents', 0)
        one_time_cost = item.pop('_one_time_cost_cents', 0)
        item['verified_forecast_comparisons'] = forecast_count
        item['forecast_mean_absolute_error_cents'] = (
            round(absolute_error_total / forecast_count, 2)
            if forecast_count else 0)
        item['forecast_mean_projected_contribution_cents'] = (
            round(projected_total / forecast_count, 2)
            if forecast_count else 0)
        sample_size = max(payment_sample, reused_opportunities, forecast_count)
        retained = item['verified_retention_receipts']
        timestamps = [
            line['occurred_at'] for line in item['receipt_lineage']]
        timestamps.extend(
            line['occurred_at'] for line in item['reuse_receipt_lineage'])
        timestamps.extend(forecast_timestamps)
        item.update({
            'observed_revenue':
                (item['realized_recurring_net_cents'] + one_time_net) / 100.0,
            'observed_cost':
                (item['realized_recurring_cost_cents'] + one_time_cost) / 100.0,
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
    buyer_stage = metrics.get('highest_active_buyer_stage')
    if buyer_stage in {'contracted', 'executing', 'qa_passed', 'delivered', 'invoiced'}:
        plan.append({
            'priority': 1,
            'action': 'advance_verified_contract_delivery',
            'mode': 'prepare',
            'buyer_stage': buyer_stage,
            'reason': 'Verified contracted work outranks prospecting until delivery and collection progress safely.',
        })
    elif buyer_stage in {'interview', 'offer'}:
        plan.append({
            'priority': 1,
            'action': 'advance_active_buyer_offer',
            'mode': 'prepare',
            'buyer_stage': buyer_stage,
            'reason': 'A verified interview or offer outranks new prospecting.',
        })
    elif buyer_stage in {'response_received', 'buyer_reply'}:
        plan.append({
            'priority': 1,
            'action': 'respond_to_active_buyer_intent',
            'mode': 'prepare',
            'buyer_stage': buyer_stage,
            'reason': 'A verified buyer response outranks new prospecting.',
        })
    elif metrics['eligible_leads'] == 0:
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
