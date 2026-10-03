#!/usr/bin/env python3
"""Emit revenue metrics without promoting unverified sales claims to revenue."""

import json
import os
import sqlite3

DB_PATH = os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")


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


def stage_totals(conn, table, amount_columns):
    """Return receipt counts and integer cents by currency for an evidence table."""
    if not table_exists(conn, table):
        return {"receipt_count": 0, "by_currency": {}}
    select_amounts = ", ".join(
        f"COALESCE(SUM({column}),0)" for column in amount_columns
    )
    rows = conn.execute(
        f"""SELECT currency, COUNT(*), {select_amounts}
            FROM {table}
            GROUP BY currency
            ORDER BY currency"""
    ).fetchall()
    by_currency = {}
    receipt_count = 0
    for row in rows:
        currency = row[0]
        count = int(row[1])
        receipt_count += count
        values = {"receipt_count": count}
        values.update(
            {column: int(row[index + 2]) for index, column in enumerate(amount_columns)}
        )
        by_currency[currency] = values
    return {"receipt_count": receipt_count, "by_currency": by_currency}


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
        "verified_collected_revenue": stage_totals(
            conn,
            "payment_receipts",
            ("gross_amount_cents", "fee_amount_cents", "net_amount_cents"),
        ),
        "verified_withdrawable_balance": stage_totals(
            conn, "payout_availability_receipts", ("amount_cents",)
        ),
        "verified_money_received": stage_totals(
            conn, "bank_receipts", ("amount_cents",)
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
