#!/usr/bin/env python3
"""Fail-closed qualification for APEX's home-services lead-intake offer.

This validates buyer-supplied discovery evidence only. It never contacts a lead,
authorizes spend, accepts a contract, or claims that an opportunity is paid or
validated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RATE_FIELDS = ("contact", "qualification", "booking", "attendance", "close")
REQUIRED_CHANNELS = {"phone", "sms", "email"}


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def qualify(payload: dict[str, Any]) -> dict[str, Any]:
    """Return auditable blockers/warnings without inferring missing evidence."""
    blockers: list[str] = []
    warnings: list[str] = []

    leads = payload.get("monthly_inbound_leads")
    if not isinstance(leads, int) or isinstance(leads, bool) or leads < 0:
        blockers.append("monthly_inbound_leads_invalid")
    elif leads < 20:
        warnings.append("monthly_inbound_leads_below_target_icp")

    for field in ("business_hours_missed_calls", "after_hours_missed_calls", "median_first_response_minutes"):
        value = payload.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            blockers.append(f"{field}_invalid")

    rates = payload.get("current_rates")
    if not isinstance(rates, dict):
        blockers.append("current_rates_missing")
    else:
        for field in RATE_FIELDS:
            value = rates.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
                blockers.append(f"current_rate_{field}_invalid")

    revenue = payload.get("average_job_revenue_cents")
    profit = payload.get("gross_profit_per_job_cents")
    if not isinstance(revenue, int) or isinstance(revenue, bool) or revenue <= 0:
        blockers.append("average_job_revenue_cents_invalid")
    if not isinstance(profit, int) or isinstance(profit, bool) or profit <= 0:
        blockers.append("gross_profit_per_job_cents_invalid")
    elif isinstance(revenue, int) and not isinstance(revenue, bool) and revenue > 0 and profit > revenue:
        blockers.append("gross_profit_exceeds_revenue")

    channels = payload.get("channels")
    if not isinstance(channels, list) or not channels or any(not _present(item) for item in channels):
        blockers.append("channels_missing")
    elif not REQUIRED_CHANNELS.intersection(item.strip().lower() for item in channels):
        blockers.append("supported_contact_channel_missing")

    for field in ("crm_or_source_of_truth", "calendar_or_scheduler", "consent_basis",
                  "human_escalation_owner", "authorized_integration_method"):
        if not _present(payload.get(field)):
            blockers.append(f"{field}_missing")

    for field in ("opt_out_process_confirmed", "quiet_hours_defined", "suppression_list_available",
                  "integration_authorized"):
        if payload.get(field) is not True:
            blockers.append(f"{field}_not_confirmed")

    sla = payload.get("human_escalation_sla_minutes")
    if not isinstance(sla, (int, float)) or isinstance(sla, bool) or sla <= 0:
        blockers.append("human_escalation_sla_minutes_invalid")

    evidence = payload.get("baseline_evidence")
    if not isinstance(evidence, list) or not evidence or any(not _present(item) for item in evidence):
        blockers.append("baseline_evidence_missing")

    if payload.get("uses_bought_or_scraped_lists") is not False:
        blockers.append("bought_or_scraped_list_status_not_disqualified")
    if payload.get("emergency_dispatch_required") is not False:
        blockers.append("emergency_dispatch_not_disqualified")
    if payload.get("guaranteed_outcome_requested") is not False:
        blockers.append("guaranteed_outcome_not_disqualified")

    return {
        "schema_version": 1,
        "offer_id": "home_services_lead_intake_booking",
        "eligible_for_scoping": not blockers,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "execution_gate": "qualified_evidence_only" if not blockers else "blocked",
        "authorized_actions": [],
        "mastery": "learned",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify a redacted home-services lead-intake opportunity")
    parser.add_argument("input", type=Path, help="Path to a redacted JSON discovery record")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        result = qualify(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"eligible_for_scoping": False, "execution_gate": "blocked", "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["eligible_for_scoping"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
