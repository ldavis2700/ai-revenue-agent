#!/usr/bin/env python3
"""Conservatively evaluate earned mastery for the lead-intake offer.

The result is a review candidate only. It never mutates the revenue ledger,
authorizes delivery, or promotes an offer without owner verification.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path


STAGES = (
    "learned",
    "validated_paid_engagement",
    "repeatable_positive_margin",
    "scale_candidate",
    "productize_candidate",
)
SENSITIVE_KEY = re.compile(
    r"(^|_)(email|phone|name|address|token|secret|password|api_key|credential)(_|$)",
    re.I,
)
SENSITIVE_VALUE = re.compile(
    r"(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b(?:\+?1[-. ]?)?\d{3}[-. ]\d{3}[-. ]\d{4}\b|\bBearer\s+\S+|\bsk_(?:live|test)_\S+)",
    re.I,
)


def _sensitive_paths(value, path="root", depth=0):
    if depth > 12:
        return [f"{path}:nesting_too_deep"]
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if SENSITIVE_KEY.search(str(key)):
                found.append(child_path)
            else:
                found.extend(_sensitive_paths(child, child_path, depth + 1))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_sensitive_paths(child, f"{path}[{index}]", depth + 1))
    elif isinstance(value, str) and SENSITIVE_VALUE.search(value):
        found.append(path)
    return found


def _nonnegative_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def evaluate(payload: dict) -> dict:
    blockers = []
    warnings = []
    sensitive = _sensitive_paths(payload)
    if sensitive:
        blockers.append("raw_secret_or_contact_data_detected")

    deliveries = payload.get("deliveries", [])
    if not isinstance(deliveries, list):
        deliveries = []
        blockers.append("deliveries_must_be_list")

    seen_ids = set()
    paid = []
    positive = []
    component_buyers = defaultdict(set)
    candidate_collected = 0
    candidate_cost = 0
    candidate_hours = 0.0

    for index, item in enumerate(deliveries):
        if not isinstance(item, dict):
            blockers.append(f"delivery_{index}_must_be_object")
            continue
        prefix = f"delivery_{index}"
        delivery_id = item.get("delivery_id")
        buyer_ref = item.get("buyer_ref")
        if not isinstance(delivery_id, str) or not delivery_id.strip():
            blockers.append(f"{prefix}_delivery_id_missing")
        elif delivery_id in seen_ids:
            blockers.append(f"duplicate_delivery_id:{delivery_id}")
        else:
            seen_ids.add(delivery_id)
        if not isinstance(buyer_ref, str) or not buyer_ref.startswith("redacted://"):
            blockers.append(f"{prefix}_redacted_buyer_ref_missing")

        revenue = item.get("collected_revenue_cents")
        delivery_cost = item.get("delivery_cost_cents")
        api_cost = item.get("api_cost_cents")
        hours = item.get("human_hours")
        for field, value in (
            ("collected_revenue_cents", revenue),
            ("delivery_cost_cents", delivery_cost),
            ("api_cost_cents", api_cost),
        ):
            if not _nonnegative_int(value):
                blockers.append(f"{prefix}_{field}_invalid")
        if not _positive_number(hours):
            blockers.append(f"{prefix}_human_hours_invalid")

        accepted = item.get("accepted_delivery") is True
        settled = item.get("settled_payment_verified") is True
        if _nonnegative_int(revenue) and revenue > 0 and not settled:
            blockers.append(f"{prefix}_revenue_without_settled_payment")
        if settled and (not _nonnegative_int(revenue) or revenue <= 0):
            blockers.append(f"{prefix}_settled_payment_without_positive_revenue")

        numeric = all((
            _nonnegative_int(revenue),
            _nonnegative_int(delivery_cost),
            _nonnegative_int(api_cost),
            _positive_number(hours),
        ))
        qualifies_paid = accepted and settled and numeric and revenue > 0
        if qualifies_paid:
            contribution = revenue - delivery_cost - api_cost
            record = {**item, "contribution_cents": contribution}
            paid.append(record)
            candidate_collected += revenue
            candidate_cost += delivery_cost + api_cost
            candidate_hours += float(hours)
            if contribution > 0:
                positive.append(record)
                if item.get("confidentiality_cleared") is True:
                    components = item.get("reusable_components", [])
                    if isinstance(components, list):
                        for component in components:
                            if isinstance(component, str) and component.strip():
                                component_buyers[component.strip()].add(buyer_ref)

    stage = "learned"
    paid_buyers = {item.get("buyer_ref") for item in paid}
    positive_buyers = {item.get("buyer_ref") for item in positive}
    if paid:
        stage = "validated_paid_engagement"
    if len(positive) >= 2 and len(positive_buyers) >= 2:
        stage = "repeatable_positive_margin"
    controls = (
        payload.get("support_risk_controlled") is True
        and payload.get("acquisition_economics_verified") is True
    )
    retained = any(item.get("retained") is True for item in positive)
    if stage == "repeatable_positive_margin" and controls and retained:
        stage = "scale_candidate"
    expanded = any(item.get("expanded") is True for item in positive)
    reused = sorted(name for name, buyers in component_buyers.items() if len(buyers) >= 2)
    all_positive_cleared = bool(positive) and all(
        item.get("confidentiality_cleared") is True for item in positive
    )
    if stage == "scale_candidate" and expanded and reused and all_positive_cleared:
        stage = "productize_candidate"

    if not paid:
        warnings.append("no_verified_paid_engagement")
    elif len(positive_buyers) < 2:
        warnings.append("two_independent_positive_margin_buyers_required")
    if stage in {"repeatable_positive_margin", "validated_paid_engagement"} and not controls:
        warnings.append("support_and_acquisition_controls_required_for_scale")
    if stage == "scale_candidate" and not (expanded and reused and all_positive_cleared):
        warnings.append("expansion_reuse_and_confidentiality_evidence_required_for_productization")

    contribution = candidate_collected - candidate_cost
    return {
        "mastery_candidate": stage,
        "evidence_record_valid": not blockers,
        "promotion_review_ready": not blockers and stage != "learned",
        "evidence_status": "redacted_assertions_require_owner_verification",
        "verified_paid_delivery_count_for_review": len(paid),
        "independent_paid_buyer_count_for_review": len(paid_buyers),
        "positive_margin_delivery_count_for_review": len(positive),
        "settled_revenue_asserted_for_review_cents": candidate_collected,
        "candidate_contribution_cents": contribution,
        "candidate_contribution_per_human_hour_cents": (
            round(contribution / candidate_hours) if candidate_hours else 0
        ),
        "reused_components_for_review": reused,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "ledger_mutation_authorized": False,
        "execution_authorized": False,
        "authorized_actions": [],
        **({"redaction_blockers": sensitive} if sensitive else {}),
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("usage: lead_intake_mastery_promotion.py INPUT.json", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("root must be object")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "invalid_input", "detail": str(exc)}))
        return 2
    result = evaluate(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["evidence_record_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
