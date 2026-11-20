#!/usr/bin/env python3
"""Fail-closed readiness review for a bounded lead-intake pilot.

Passing this review never authorizes execution. It only confirms that a redacted
record is complete enough for an authorized owner to make a go/no-go decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lead_intake_qualification import sensitive_paths


REVENUE_STAGES = (
    "prospect",
    "qualified_opportunity",
    "proposal",
    "buyer_reply_interview",
    "offer",
    "contract",
    "funded_billable_work",
    "delivered_work",
    "invoiced_approved",
    "collected_revenue",
    "withdrawable_balance",
    "money_received",
)
FUNDED_INDEX = REVENUE_STAGES.index("funded_billable_work")
COLLECTED_INDEX = REVENUE_STAGES.index("collected_revenue")

REQUIRED_TRUE = (
    "scope_accepted",
    "contract_verified",
    "payment_protection_verified",
    "integration_authorized",
    "consent_controls_verified",
    "suppression_verified",
    "quiet_hours_verified",
    "human_escalation_verified",
    "source_of_truth_verified",
    "rollback_tested",
)
REQUIRED_TEXT = (
    "scope_evidence_ref",
    "contract_evidence_ref",
    "payment_evidence_ref",
    "authorized_integration_ref",
    "source_of_truth",
    "human_escalation_owner",
    "rollback_evidence_ref",
)
REQUIRED_POSITIVE_INTS = (
    "pilot_days",
    "max_records",
    "max_external_actions",
    "max_api_spend_cents",
)
REQUIRED_QA = (
    "consent_and_suppression",
    "quiet_hours_and_timezone",
    "duplicate_and_idempotency",
    "unsafe_and_emergency_language",
    "prompt_injection",
    "integration_failure",
    "audit_lineage",
    "rollback",
)


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def review(payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    redaction_blockers = sensitive_paths(payload)
    if redaction_blockers:
        blockers.append("raw_secret_or_contact_data_detected")

    stage = payload.get("revenue_stage")
    if stage not in REVENUE_STAGES:
        blockers.append("revenue_stage_invalid")
        stage_index = -1
    else:
        stage_index = REVENUE_STAGES.index(stage)

    for field in REQUIRED_TRUE:
        if payload.get(field) is not True:
            blockers.append(f"{field}_not_verified")

    for field in REQUIRED_TEXT:
        if not _present(payload.get(field)):
            blockers.append(f"{field}_missing")

    for field in REQUIRED_POSITIVE_INTS:
        value = payload.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            blockers.append(f"{field}_invalid")

    qa = payload.get("qa_gates")
    if not isinstance(qa, dict):
        blockers.append("qa_gates_missing")
    else:
        for gate in REQUIRED_QA:
            if qa.get(gate) is not True:
                blockers.append(f"qa_{gate}_not_passed")

    if stage_index < FUNDED_INDEX:
        blockers.append("funded_billable_work_not_verified")
    if not _present(payload.get("funding_evidence_ref")):
        blockers.append("funding_evidence_ref_missing")

    settled = payload.get("settled_payment_verified")
    if not isinstance(settled, bool):
        blockers.append("settled_payment_verified_invalid")
    elif stage_index >= COLLECTED_INDEX and not settled:
        blockers.append("collected_stage_requires_settled_payment")
    elif stage_index < COLLECTED_INDEX and settled:
        blockers.append("settled_payment_precedes_collected_stage")

    collected = payload.get("collected_revenue_cents")
    if not isinstance(collected, int) or isinstance(collected, bool) or collected < 0:
        blockers.append("collected_revenue_cents_invalid")
    elif collected > 0 and (stage_index < COLLECTED_INDEX or settled is not True):
        blockers.append("collected_revenue_not_verified")
    elif stage_index < COLLECTED_INDEX and collected != 0:
        blockers.append("pre_collection_revenue_must_be_zero")

    result = {
        "schema_version": 1,
        "offer_id": "home_services_lead_intake_booking",
        "owner_review_ready": not blockers,
        "execution_authorized": False,
        "authorized_actions": [],
        "blockers": sorted(set(blockers)),
        "revenue_stage": stage if stage in REVENUE_STAGES else "invalid",
        "collected_revenue_cents": collected if isinstance(collected, int) and not isinstance(collected, bool) and collected >= 0 else 0,
        "mastery": "learned",
        "next_action": "authorized_owner_go_no_go_review" if not blockers else "resolve_blockers",
    }
    if redaction_blockers:
        result["redaction_blockers"] = redaction_blockers
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Review redacted bounded-pilot readiness evidence")
    parser.add_argument("input", type=Path, help="Path to a redacted JSON readiness record")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        result = review(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({
            "owner_review_ready": False,
            "execution_authorized": False,
            "authorized_actions": [],
            "error": str(exc),
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["owner_review_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
