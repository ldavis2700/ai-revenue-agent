#!/usr/bin/env python3
"""Read-only wealth expertise audit from APEX's local receipt ledger.

This is an evaluation and next-action selector, not a model trainer or payment
provider verification. Missing tables/data are UNKNOWN, never zero income.
"""
import argparse
import json
import sqlite3
from pathlib import Path


def has_columns(db, table, required):
    if table not in {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}:
        return False
    columns={row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    return set(required).issubset(columns)


def valid_receipts(db, table):
    names=("receipt_id","gross_amount_cents","fee_amount_cents","net_amount_cents")
    if not has_columns(db,table,names):
        return {"state":"unavailable","receipts":None,"gross_cents":None,
                "fees_cents":None,"net_cents":None,"integrity_issues":[]}
    rows=db.execute(f"SELECT {','.join(names)} FROM {table}").fetchall()
    seen=set()
    issues=[]
    totals=[0,0,0]
    for row in rows:
        rid,gross,fee,net=row
        if not isinstance(rid,str) or not rid or rid in seen:
            issues.append("duplicate_or_missing_receipt_id");continue
        seen.add(rid)
        if any(type(v) is not int or v<0 for v in (gross,fee,net)):
            issues.append("invalid_receipt_amount");continue
        if net!=gross-fee:
            issues.append("unreconciled_fee_arithmetic");continue
        totals=[a+b for a,b in zip(totals,(gross,fee,net))]
    # Never report cash totals while ANY integrity issue is unresolved.
    if issues:
        return {"state":"unreconciled","receipts":None,"gross_cents":None,
                "fees_cents":None,"net_cents":None,"integrity_issues":sorted(set(issues))}
    return {"state":"locally_reconciled","receipts":len(rows),
            "gross_cents":totals[0],"fees_cents":totals[1],
            "net_cents":totals[2],"integrity_issues":[],
            "provider_settlement_independently_checked":False}


def recurring_contribution(db):
    table="recurring_realized_unit_economics"
    if not has_columns(db,table,("recurring_payment_receipt_id","contribution_cents")):
        return {"state":"unavailable","positive_periods":None,"distinct_paid_periods":None}
    rows=db.execute(f"SELECT recurring_payment_receipt_id,contribution_cents FROM {table}").fetchall()
    # Local contribution rows must link to an actual recurring receipt in this ledger.
    if not has_columns(db,"recurring_payment_receipts",("receipt_id",)):
        return {"state":"unavailable","positive_periods":None,"distinct_paid_periods":None}
    linked={row[0] for row in db.execute("SELECT receipt_id FROM recurring_payment_receipts")}
    if any(receipt not in linked for receipt,_ in rows):
        return {"state":"unreconciled","positive_periods":None,"distinct_paid_periods":None}
    ids=set()
    positive=set()
    for receipt,contribution in rows:
        if not isinstance(receipt,str) or not receipt or receipt in ids:
            return {"state":"unreconciled","positive_periods":None,"distinct_paid_periods":None}
        ids.add(receipt)
        if type(contribution) is not int:
            return {"state":"unreconciled","positive_periods":None,"distinct_paid_periods":None}
        if contribution>0:positive.add(receipt)
    return {"state":"locally_reconciled",
            "positive_periods":len(positive),"distinct_paid_periods":len(ids),
            "provider_settlement_independently_checked":False}


def audit(db):
    one=valid_receipts(db,"payment_receipts")
    recurring=valid_receipts(db,"recurring_payment_receipts")
    economics=recurring_contribution(db)
    # The same provider receipt must not be counted once as a setup payment and
    # again as recurring cash, even when each table is internally consistent.
    if one["state"]==recurring["state"]=="locally_reconciled":
        one_ids={r[0] for r in db.execute("SELECT receipt_id FROM payment_receipts")}
        recurring_ids={r[0] for r in db.execute("SELECT receipt_id FROM recurring_payment_receipts")}
        if one_ids & recurring_ids:
            for result in (one,recurring):
                result.update(state="unreconciled",receipts=None,gross_cents=None,
                              fees_cents=None,net_cents=None,
                              integrity_issues=["cross_table_duplicate_receipt_id"])
    if one["state"]=="unreconciled" or recurring["state"]=="unreconciled" or economics["state"]=="unreconciled":
        next_step="Reconcile receipt IDs, amounts and period economics against original provider statements; quarantine uncertain results."
        stage="reconciliation_required"
    elif one["state"]=="unavailable" or recurring["state"]=="unavailable":
        next_step="Verify deployed ledger schema and connected collection coverage; do not infer zero collected revenue from absent tables."
        stage="coverage_unknown"
    elif one["receipts"]+recurring["receipts"]==0:
        next_step="Prioritize a real buyer request, accepted scoped delivery and a verified authorized non-Stripe payment/settlement path."
        stage="first_paid_delivery_unverified"
    elif economics["state"]=="unavailable" or economics["positive_periods"]<2:
        next_step="Validate full service and support costs for two distinct paid customer periods; do not assume positive recurring margin."
        stage="recurring_unit_economics_unverified"
    else:
        next_step="Independently verify provider settlement and customer-level retention before expanding scale or acquisition spend."
        stage="repeatability_under_review"
    return {"stage":stage,
            "one_time_receipts":one,
            "recurring_receipts":recurring,
            "recurring_economics":economics,
            "next_executable_bottleneck":next_step,
            "evidence_scope":"local_ledger_only",
            "external_provider_receipts_verified_by_this_audit":False,
            "money_received_in_owner_bank":"unknown",
            "personal_wealth":"unknown",
            "expertise_status":"not_proven",
            "external_actions_taken":False,
            "approval_gates_unchanged":True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",required=True)
    args=parser.parse_args()
    if not Path(args.db).exists():
        raise SystemExit("No existing APEX ledger: refusing to create an empty database")
    uri=Path(args.db).resolve().as_uri()+"?mode=ro"
    with sqlite3.connect(uri,uri=True) as db:
        print(json.dumps(audit(db),indent=2))


if __name__=="__main__":
    main()
