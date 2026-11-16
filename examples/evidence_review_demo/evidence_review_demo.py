#!/usr/bin/env python3
"""Synthetic, offline evidence -> human review -> structured record demo.

Never uses buyer data, credentials, network services, or production Supabase.
The result demonstrates approval gating, source provenance and a local SQL write.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass(frozen=True)
class Evidence:
    source_id: str
    source_text: str
    source_reference: str


@dataclass(frozen=True)
class Proposal:
    field_name: str
    proposed_value: str
    source_id: str
    source_reference: str
    support_quote: str


def propose(evidence: Evidence, field_name: str, value: str, support_quote: str) -> Proposal:
    """Only permit a proposal with a direct, inspectable source quote."""
    for item in (evidence.source_id, evidence.source_reference, field_name, value, support_quote):
        if not isinstance(item, str) or not item.strip() or len(item) > 2000:
            raise ValueError("All fields must be nonempty bounded strings")
    if support_quote not in evidence.source_text:
        raise ValueError("Supporting quote must be an exact substring of the source")
    if len(evidence.source_text) > 50000:
        raise ValueError("Source too long for this small demo")
    return Proposal(field_name, value, evidence.source_id, evidence.source_reference, support_quote)


def initialize(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS approved_records (
        id INTEGER PRIMARY KEY,
        field_name TEXT NOT NULL,
        approved_value TEXT NOT NULL,
        review_decision TEXT NOT NULL CHECK(review_decision IN ('approved','corrected')),
        original_proposal TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_reference TEXT NOT NULL,
        support_quote TEXT NOT NULL,
        reviewed_at_utc TEXT NOT NULL
    )""")


def review_and_save(
    connection: sqlite3.Connection, proposal: Proposal,
    decision: Literal["approve", "correct", "reject"],
    corrected_value: str | None = None,
) -> int | None:
    """Persist only reviewed records. Rejected suggestions never enter output table."""
    if decision not in ("approve", "correct", "reject"):
        raise ValueError("Unsupported decision")
    if decision == "reject":
        return None
    if decision == "correct":
        if not isinstance(corrected_value, str) or not corrected_value.strip() or len(corrected_value) > 2000:
            raise ValueError("Corrections require a bounded nonempty replacement")
        value = corrected_value.strip()
    else:
        if corrected_value is not None:
            raise ValueError("Do not supply a correction when approving unchanged")
        value = proposal.proposed_value
    initialize(connection)
    with connection:
        cursor = connection.execute("""INSERT INTO approved_records
            (field_name, approved_value, review_decision, original_proposal,
             source_id, source_reference, support_quote, reviewed_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
                proposal.field_name, value,
                "corrected" if decision == "correct" else "approved",
                proposal.proposed_value, proposal.source_id, proposal.source_reference,
                proposal.support_quote, datetime.now(timezone.utc).isoformat(),
            ))
    return int(cursor.lastrowid)


def example(decision: str = "approve", corrected_value: str | None = None) -> dict:
    evidence = Evidence(
        "synthetic-001",
        "EXAMPLE ONLY: Invoice 001 has total USD 240.00; no customer involved.",
        "local://synthetic-001",
    )
    item = propose(evidence, "invoice_total", "240.00 USD", "total USD 240.00")
    with sqlite3.connect(":memory:") as db:
        record_id = review_and_save(db, item, decision, corrected_value)
        if record_id is None:
            return {"decision": "rejected", "record_saved": False}
        row = db.execute("""SELECT field_name, approved_value, review_decision,
                source_id, source_reference, support_quote
                FROM approved_records WHERE id=?""", (record_id,)).fetchone()
    fields = ("field_name", "approved_value", "review_decision", "source_id",
              "source_reference", "support_quote")
    return {"record_saved": True, "record": dict(zip(fields, row))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", choices=("approve", "correct", "reject"), default="approve")
    parser.add_argument("--corrected-value")
    args = parser.parse_args()
    if args.decision != "correct" and args.corrected_value is not None:
        parser.error("--corrected-value only applies to --decision correct")
    try:
        print(json.dumps(example(args.decision, args.corrected_value), indent=2))
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
