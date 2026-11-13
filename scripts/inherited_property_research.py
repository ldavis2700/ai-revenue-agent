#!/usr/bin/env python3
"""Daily, research-only inherited-property wholesaling evaluation.

Input is a JSON document containing jurisdiction_clearance, records and source
metadata. No scraping, contact, contracts or money movement occurs here.
No externally sourced properties are implied when the input is absent.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MODEL_ID = "inherited_residential_wholesaling"
REQUIRED_CLEARANCE = {
    "licensing", "assignments", "advertising", "probate_authority",
    "privacy_and_outreach", "title_and_closing",
}


def assess(record: dict, clearance: dict) -> dict:
    result = {"parcel_id": str(record.get("parcel_id") or ""), "qualified": False,
              "reasons": [], "potential_fee": 0.0, "collected_revenue": 0.0}
    reasons = result["reasons"]
    if not all(clearance.get(key) is True for key in REQUIRED_CLEARANCE):
        reasons.append("jurisdiction_not_cleared")
    if not result["parcel_id"] or not record.get("source_url") or not record.get("source_date"):
        reasons.append("missing_source_or_parcel_id")
    if record.get("estate_related") and record.get("seller_authority_verified") is not True:
        reasons.append("estate_sale_authority_unverified")
    if record.get("seller_authority_verified") is not True:
        reasons.append("seller_authority_unverified")
    if record.get("marketable_interest_verified") is not True:
        reasons.append("no_marketable_interest")
    comps = record.get("closed_comps") or []
    if not isinstance(comps, list) or len(comps) < 2 or any(
        not isinstance(c, dict) or not c.get("closed_date") or not c.get("source_url")
        or not isinstance(c.get("sold_price"), (int, float)) or c["sold_price"] <= 0
        for c in comps
    ):
        reasons.append("insufficient_verified_closed_comps")
    financial_keys = ("supported_buyer_price", "purchase_price", "closing_costs",
                      "repairs", "holding_costs", "buyer_margin", "uncertainty_reserve")
    if any(not isinstance(record.get(k), (int, float)) or isinstance(record.get(k), bool)
           or record[k] < 0 for k in financial_keys):
        reasons.append("invalid_financial_inputs")
    if not reasons:
        potential = (record["supported_buyer_price"] - record["purchase_price"]
                     - sum(record[k] for k in financial_keys[2:]))
        if potential <= 0:
            reasons.append("nonpositive_downside_margin")
        else:
            result["potential_fee"] = round(potential, 2)
            result["qualified"] = True
    return result


def evaluate(payload: dict) -> dict:
    clearance = payload.get("jurisdiction_clearance") or {}
    records = payload.get("records") or []
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    seen, results = set(), []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each record must be an object")
        parcel = str(record.get("parcel_id") or "")
        if parcel and parcel in seen:
            results.append({"parcel_id": parcel, "qualified": False,
                            "reasons": ["duplicate_parcel"], "potential_fee": 0.0,
                            "collected_revenue": 0.0})
            continue
        seen.add(parcel)
        results.append(assess(record, clearance))
    return {
        "model_id": MODEL_ID, "mode": "research_only", "source": payload.get("source") or "none",
        "jurisdiction": payload.get("jurisdiction") or "unspecified",
        "jurisdiction_cleared": all(clearance.get(k) is True for k in REQUIRED_CLEARANCE),
        "evaluated": len(results), "qualified": sum(r["qualified"] for r in results),
        "collected_revenue": 0.0, "external_actions_allowed": False,
        "results": results,
    }


def persist(db_path: str, day: str, report: dict) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS model_research_daily (
            model_id TEXT NOT NULL, run_day TEXT NOT NULL,
            jurisdiction TEXT NOT NULL, report_json TEXT NOT NULL,
            PRIMARY KEY (model_id, run_day, jurisdiction)
        )""")
        conn.execute("""INSERT INTO model_research_daily
            (model_id, run_day, jurisdiction, report_json) VALUES (?, ?, ?, ?)
            ON CONFLICT(model_id, run_day, jurisdiction) DO UPDATE
            SET report_json=excluded.report_json""",
            (MODEL_ID, day, report["jurisdiction"], json.dumps(report, sort_keys=True)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="authorized, dated source data as JSON")
    parser.add_argument("--db", help="existing APEX revenue DB path")
    parser.add_argument("--day", default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()
    payload = json.loads(args.input.read_text()) if args.input else {}
    report = evaluate(payload)
    if args.db:
        persist(args.db, args.day, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
