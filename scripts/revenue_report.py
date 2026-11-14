#!/usr/bin/env python3
"""Emit revenue metrics without promoting unverified sales claims to revenue."""

import importlib.util
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")


def _load_intake_verifiers():
    """Load the sibling ledger module regardless of the caller's sys.path."""
    path = Path(__file__).with_name("opportunity_intake.py")
    spec = importlib.util.spec_from_file_location(
        "revenue_report_opportunity_intake", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        module._verified_payment_receipt,
        module._verified_payout_receipt,
        module._verified_bank_receipt,
    )


(
    _verified_payment_receipt,
    _verified_payout_receipt,
    _verified_bank_receipt,
) = _load_intake_verifiers()


def table_exists(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def count_event(conn, event_type):
    if not table_exists(conn, "events"):
        return 0
    return conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_type=?", (event_type,)
    ).fetchone()[0]


def sum_event_value(conn, event_type):
    if not table_exists(conn, "events"):
        return 0
    return conn.execute(
        "SELECT COALESCE(SUM(value),0) FROM events WHERE event_type=?",
        (event_type,),
    ).fetchone()[0]


def verified_stage_totals(
    conn,
    table,
    amount_columns,
    verifier,
    currency_index,
    amount_indexes,
):
    """Aggregate only receipts whose immutable snapshot and lineage re-verify."""
    if not table_exists(conn, table):
        return {
            "receipt_count": 0,
            "unverified_receipt_count": 0,
            "by_currency": {},
        }

    receipt_ids = conn.execute(
        f"SELECT receipt_id FROM {table} ORDER BY receipt_id"
    ).fetchall()
    by_currency = {}
    verified_count = 0
    unverified_count = 0
    for (receipt_id,) in receipt_ids:
        try:
            receipt = verifier(conn, receipt_id)
            currency = receipt[currency_index]
            amounts = [
                int(receipt[index])
                for index in amount_indexes
            ]
        except (
            IndexError,
            TypeError,
            ValueError,
            sqlite3.DatabaseError,
        ):
            unverified_count += 1
            continue

        verified_count += 1
        totals = by_currency.setdefault(
            currency,
            {
                "receipt_count": 0,
                **{column: 0 for column in amount_columns},
            },
        )
        totals["receipt_count"] += 1
        for column, amount in zip(amount_columns, amounts):
            totals[column] += amount

    return {
        "receipt_count": verified_count,
        "unverified_receipt_count": unverified_count,
        "by_currency": dict(sorted(by_currency.items())),
    }


def pipeline_counts(conn):
    if not table_exists(conn, "opportunities"):
        return {}
    return {
        state: int(count)
        for state, count in conn.execute(
            """SELECT pipeline_state, COUNT(*)
               FROM opportunities
               GROUP BY pipeline_state
               ORDER BY pipeline_state"""
        )
    }


def build_report(conn, min_lead_score=55):
    leads = (
        conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        if table_exists(conn, "leads")
        else 0
    )
    qualified = (
        conn.execute(
            "SELECT COUNT(*) FROM leads WHERE score >= ?", (min_lead_score,)
        ).fetchone()[0]
        if table_exists(conn, "leads")
        else 0
    )
    sent = count_event(conn, "sent")
    replies = count_event(conn, "reply")
    interested = count_event(conn, "interested")
    meetings = count_event(conn, "meeting")

    claimed_sales = count_event(conn, "sale")
    claimed_gross = sum_event_value(conn, "sale")
    claimed_refunds = sum_event_value(conn, "refund")

    def rate(numerator, denominator):
        return round((numerator / denominator * 100), 2) if denominator else 0.0

    return {
        "leads": leads,
        "qualified": qualified,
        "sent": sent,
        "replies": replies,
        "interested": interested,
        "meetings": meetings,
        "reply_rate_pct": rate(replies, sent),
        "interest_rate_pct": rate(interested, replies),
        "claimed_sales": {
            "event_count": claimed_sales,
            "claimed_gross_value": claimed_gross,
            "claimed_refund_value": claimed_refunds,
            "claimed_net_value": claimed_gross - claimed_refunds,
            "status": "unverified_not_collected_revenue",
        },
        "verified_collected_revenue": verified_stage_totals(
            conn,
            "payment_receipts",
            ("gross_amount_cents", "fee_amount_cents", "net_amount_cents"),
            _verified_payment_receipt,
            8,
            (5, 6, 7),
        ),
        "verified_withdrawable_balance": verified_stage_totals(
            conn,
            "payout_availability_receipts",
            ("amount_cents",),
            _verified_payout_receipt,
            6,
            (5,),
        ),
        "verified_money_received": verified_stage_totals(
            conn,
            "bank_receipts",
            ("amount_cents",),
            _verified_bank_receipt,
            6,
            (5,),
        ),
        "pipeline_state_counts": pipeline_counts(conn),
    }


def main():
    connection = sqlite3.connect(DB_PATH)
    try:
        report = build_report(
            connection, int(os.getenv("MIN_LEAD_SCORE", "55"))
        )
    finally:
        connection.close()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
