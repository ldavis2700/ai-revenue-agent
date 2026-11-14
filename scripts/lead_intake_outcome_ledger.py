#!/usr/bin/env python3
"""Audit a proposed outcome-pricing ledger without authorizing billing.

All calculated fees are review estimates. They are never invoices, charges,
collected revenue, withdrawable funds, or money received.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from lead_intake_qualification import sensitive_paths


ALLOWED_EVENTS = {
    "attended_appointment",
    "completed_job",
    "recovered_completed_job",
}


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value: Any) -> datetime | None:
    if not _present(value):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def audit(payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    redaction_blockers = sensitive_paths(payload)
    if redaction_blockers:
        blockers.append("raw_secret_or_contact_data_detected")

    for field in (
        "paid_pilot_accepted",
        "pilot_settled_payment_verified",
        "outcome_terms_accepted",
    ):
        if payload.get(field) is not True:
            blockers.append(f"{field}_not_verified")

    for field in (
        "pilot_acceptance_evidence_ref",
        "pilot_payment_evidence_ref",
        "outcome_terms_evidence_ref",
        "source_of_truth",
        "attribution_exclusions",
        "dispute_process",
        "human_escalation_owner",
    ):
        if field == "attribution_exclusions":
            exclusions = payload.get(field)
            if not isinstance(exclusions, list) or not exclusions or any(not _present(item) for item in exclusions):
                blockers.append("attribution_exclusions_missing")
        elif not _present(payload.get(field)):
            blockers.append(f"{field}_missing")

    event_type = payload.get("objective_billable_event")
    if event_type not in ALLOWED_EVENTS:
        blockers.append("objective_billable_event_invalid")

    start = _timestamp(payload.get("attribution_window_start"))
    end = _timestamp(payload.get("attribution_window_end"))
    if start is None:
        blockers.append("attribution_window_start_invalid")
    if end is None:
        blockers.append("attribution_window_end_invalid")
    if start is not None and end is not None and start >= end:
        blockers.append("attribution_window_invalid")

    fee = payload.get("fee_per_event_cents")
    cap = payload.get("monthly_cap_cents")
    review_days = payload.get("buyer_review_window_days")
    if not isinstance(fee, int) or isinstance(fee, bool) or fee <= 0:
        blockers.append("fee_per_event_cents_invalid")
        fee = 0
    if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
        blockers.append("monthly_cap_cents_invalid")
        cap = 0
    if fee and cap and cap < fee:
        blockers.append("monthly_cap_below_single_event_fee")
    if not isinstance(review_days, int) or isinstance(review_days, bool) or review_days <= 0:
        blockers.append("buyer_review_window_days_invalid")

    events = payload.get("events")
    if not isinstance(events, list):
        blockers.append("events_invalid")
        events = []

    seen: set[str] = set()
    eligible_ids: list[str] = []
    excluded_ids: list[str] = []
    disputed_ids: list[str] = []
    for index, event in enumerate(events):
        prefix = f"event_{index}"
        if not isinstance(event, dict):
            blockers.append(f"{prefix}_invalid")
            continue
        event_id = event.get("event_id")
        if not _present(event_id):
            blockers.append(f"{prefix}_id_missing")
            continue
        if event_id in seen:
            blockers.append(f"duplicate_event_id:{event_id}")
            continue
        seen.add(event_id)

        if not _present(event.get("source_evidence_ref")):
            blockers.append(f"{prefix}_source_evidence_missing")
        occurred = _timestamp(event.get("occurred_at"))
        if occurred is None:
            blockers.append(f"{prefix}_occurred_at_invalid")
        outside_window = start is not None and end is not None and occurred is not None and not (start <= occurred < end)

        excluded = event.get("excluded")
        disputed = event.get("disputed")
        buyer_verified = event.get("buyer_verified")
        attributable = event.get("attributable")
        if not all(isinstance(value, bool) for value in (excluded, disputed, buyer_verified, attributable)):
            blockers.append(f"{prefix}_decision_flags_invalid")
            continue

        if excluded:
            if not _present(event.get("exclusion_reason")):
                blockers.append(f"{prefix}_exclusion_reason_missing")
            excluded_ids.append(event_id)
            continue
        if outside_window:
            blockers.append(f"{prefix}_outside_attribution_window_not_excluded")
            continue
        if event.get("event_type") != event_type:
            blockers.append(f"{prefix}_event_type_mismatch_not_excluded")
            continue
        if disputed:
            if not _present(event.get("dispute_evidence_ref")):
                blockers.append(f"{prefix}_dispute_evidence_missing")
            disputed_ids.append(event_id)
            continue
        if not buyer_verified or not attributable:
            excluded_ids.append(event_id)
            continue
        eligible_ids.append(event_id)

    gross_estimate = len(eligible_ids) * fee
    capped_estimate = min(gross_estimate, cap) if cap else 0
    result = {
        "schema_version": 1,
        "offer_id": "home_services_lead_intake_booking",
        "outcome_pricing_ready_for_owner_review": not blockers,
        "billing_authorized": False,
        "authorized_actions": [],
        "blockers": sorted(set(blockers)),
        "eligible_event_count": len(eligible_ids),
        "eligible_event_ids": sorted(eligible_ids),
        "excluded_event_ids": sorted(excluded_ids),
        "disputed_event_ids": sorted(disputed_ids),
        "estimated_outcome_fee_cents": capped_estimate,
        "estimated_outcome_fee_status": "review_only_not_billable",
        "collected_revenue_cents": 0,
        "withdrawable_balance_cents": 0,
        "money_received_cents": 0,
        "mastery": "learned",
        "next_action": "authorized_owner_and_buyer_review" if not blockers else "resolve_blockers",
    }
    if redaction_blockers:
        result["redaction_blockers"] = redaction_blockers
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a redacted proposed outcome ledger")
    parser.add_argument("input", type=Path, help="Path to a redacted JSON outcome ledger")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        result = audit(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({
            "outcome_pricing_ready_for_owner_review": False,
            "billing_authorized": False,
            "authorized_actions": [],
            "error": str(exc),
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["outcome_pricing_ready_for_owner_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
