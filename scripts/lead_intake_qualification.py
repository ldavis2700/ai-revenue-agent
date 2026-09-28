#!/usr/bin/env python3
"""Fail-closed qualification for APEX's home-services lead-intake offer.

This validates buyer-supplied discovery evidence only. It never contacts a lead,
authorizes spend, accepts a contract, or claims that an opportunity is paid or
validated.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

RATE_FIELDS = ("contact", "qualification", "booking", "attendance", "close")
REQUIRED_CHANNELS = {"phone", "sms", "email"}
PRICE_BANDS_CENTS = {
    "diagnostic_price_cents": (25000, 50000),
    "implementation_price_cents": (150000, 300000),
    "monthly_fee_cents": (50000, 150000),
}
SENSITIVE_KEY_TOKENS = {
    "access_token", "refresh_token", "api_key", "apikey", "password", "secret",
    "private_key", "session_cookie", "device_token", "customer_email",
    "customer_phone", "lead_email", "lead_phone",
}
EMAIL_PATTERN = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d)")
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{8,}\b"),
)


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def sensitive_paths(value: Any, path: str = "$", depth: int = 0) -> list[str]:
    """Return paths containing raw credentials/contact data, never their values."""
    if depth > 12:
        return [f"{path}:nesting_too_deep"]
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            normalized = re.sub(r"[^a-z0-9]+", "_", key_text.lower()).strip("_")
            child = f"{path}.{key_text}"
            if any(token in normalized for token in SENSITIVE_KEY_TOKENS):
                found.append(f"{child}:sensitive_key")
            found.extend(sensitive_paths(item, child, depth + 1))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(sensitive_paths(item, f"{path}[{index}]", depth + 1))
    elif isinstance(value, str):
        if EMAIL_PATTERN.search(value):
            found.append(f"{path}:email")
        if PHONE_PATTERN.search(value):
            found.append(f"{path}:phone")
        if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
            found.append(f"{path}:credential")
    return sorted(set(found))


def evaluate_economics(value: Any) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Validate estimate-only economics without promoting projected revenue."""
    if value is None:
        return None, [], ["economics_not_supplied_for_pricing"]
    if not isinstance(value, dict):
        return None, ["economics_invalid"], []

    blockers: list[str] = []
    warnings: list[str] = []
    required_cents = (
        "diagnostic_price_cents", "implementation_price_cents", "monthly_fee_cents",
        "initial_delivery_cost_cents", "monthly_delivery_cost_cents",
        "estimated_initial_api_cost_cents", "estimated_monthly_api_cost_cents",
        "estimated_cac_cents",
    )
    for field in required_cents:
        amount = value.get(field)
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            blockers.append(f"{field}_invalid")

    for field in ("estimated_initial_human_hours", "estimated_monthly_human_hours"):
        hours = value.get(field)
        if not isinstance(hours, (int, float)) or isinstance(hours, bool) or hours <= 0:
            blockers.append(f"{field}_invalid")

    if blockers:
        return None, blockers, warnings

    for field, (low, high) in PRICE_BANDS_CENTS.items():
        if not low <= value[field] <= high:
            warnings.append(f"{field}_outside_test_band")

    initial_revenue = value["diagnostic_price_cents"] + value["implementation_price_cents"]
    initial_cost = (
        value["initial_delivery_cost_cents"]
        + value["estimated_initial_api_cost_cents"]
        + value["estimated_cac_cents"]
    )
    monthly_cost = value["monthly_delivery_cost_cents"] + value["estimated_monthly_api_cost_cents"]
    initial_contribution = initial_revenue - initial_cost
    monthly_contribution = value["monthly_fee_cents"] - monthly_cost
    if initial_contribution <= 0:
        warnings.append("initial_contribution_not_positive")
    if monthly_contribution <= 0:
        warnings.append("monthly_contribution_not_positive")

    return {
        "status": "estimate_only",
        "initial_revenue_cents": initial_revenue,
        "initial_cost_cents": initial_cost,
        "initial_contribution_cents": initial_contribution,
        "initial_contribution_margin": round(initial_contribution / initial_revenue, 4)
        if initial_revenue else None,
        "initial_contribution_per_human_hour_cents": round(
            initial_contribution / value["estimated_initial_human_hours"]
        ),
        "monthly_recurring_revenue_cents": value["monthly_fee_cents"],
        "monthly_cost_cents": monthly_cost,
        "monthly_contribution_cents": monthly_contribution,
        "monthly_contribution_margin": round(
            monthly_contribution / value["monthly_fee_cents"], 4
        ) if value["monthly_fee_cents"] else None,
        "monthly_contribution_per_human_hour_cents": round(
            monthly_contribution / value["estimated_monthly_human_hours"]
        ),
        "collected_revenue_cents": 0,
    }, blockers, warnings


def qualify(payload: dict[str, Any]) -> dict[str, Any]:
    """Return auditable blockers/warnings without inferring missing evidence."""
    blockers: list[str] = []
    warnings: list[str] = []
    redaction_blockers = sensitive_paths(payload)
    if redaction_blockers:
        blockers.append("raw_secret_or_contact_data_detected")

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

    economics, economics_blockers, economics_warnings = evaluate_economics(payload.get("economics"))
    blockers.extend(economics_blockers)
    warnings.extend(economics_warnings)

    result = {
        "schema_version": 1,
        "offer_id": "home_services_lead_intake_booking",
        "eligible_for_scoping": not blockers,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "execution_gate": "qualified_evidence_only" if not blockers else "blocked",
        "authorized_actions": [],
        "mastery": "learned",
    }
    if economics is not None:
        result["economics"] = economics
    if redaction_blockers:
        result["redaction_blockers"] = redaction_blockers
    return result


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
