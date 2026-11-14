#!/usr/bin/env python3
"""Fail-closed evaluation of AI-built app and bespoke app-service opportunities.

Offline, standard-library only. Takes operator-supplied evidence; does not scrape,
contact buyers, build/deploy apps, charge customers or claim settled revenue.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = ("candidate_id", "lane", "buyer_problem", "buyer_evidence_url",
            "buyer_evidence_observed_at", "permission_to_use_evidence",
            "original_solution", "estimated_build_hours", "estimated_monthly_cost_usd",
            "customer_acquisition_channel", "customer_acquisition_permission",
            "technical_feasibility_review", "privacy_security_review",
            "platform_policy_review", "monetization_review")
LANES = ("owned_subscription_app", "bespoke_paid_app_service")

def _valid_date(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.tzinfo is not None and dt <= datetime.now(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return False

def _https(value):
    return isinstance(value, str) and value.startswith("https://") and len(value) > 9

def assess(candidate):
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    missing = [key for key in REQUIRED if key not in candidate]
    if missing:
        return {"candidate_id": candidate.get("candidate_id"), "state": "blocked",
                "reasons": ["missing:" + key for key in missing],
                "next_action": "supply_missing_evidence", "external_actions_allowed": False}
    reasons = []
    if candidate["lane"] not in LANES:
        reasons.append("invalid_lane")
    if not all(isinstance(candidate[k], str) and candidate[k].strip()
               for k in ("candidate_id", "buyer_problem", "original_solution",
                         "customer_acquisition_channel")):
        reasons.append("missing_description")
    if not _https(candidate["buyer_evidence_url"]) or not _valid_date(candidate["buyer_evidence_observed_at"]):
        reasons.append("unverified_or_undated_demand_source")
    for key in ("permission_to_use_evidence", "customer_acquisition_permission",
                "technical_feasibility_review", "privacy_security_review",
                "platform_policy_review", "monetization_review"):
        if candidate[key] is not True:
            reasons.append("unreviewed:" + key)
    for key in ("estimated_build_hours", "estimated_monthly_cost_usd"):
        value = candidate[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            reasons.append("invalid:" + key)
    if candidate["lane"] == "bespoke_paid_app_service":
        if not _https(candidate.get("buyer_scope_evidence_url")):
            reasons.append("no_buyer_scope_evidence")
    if candidate["lane"] == "owned_subscription_app":
        if not candidate.get("distribution_test_defined"):
            reasons.append("no_distribution_test")
        if not candidate.get("retention_test_defined"):
            reasons.append("no_retention_test")
    return {
        "candidate_id": candidate["candidate_id"],
        "lane": candidate["lane"],
        "state": "blocked" if reasons else "pilot_preparation_candidate",
        "reasons": reasons,
        "next_action": "address_evidence_gaps" if reasons else "prepare_original_offline_pilot_and_QA",
        "external_actions_allowed": False,
        "monetization_activated": False,
        "collected_revenue_usd": None,
        "profit_usd": None
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Private JSON object or list of candidates")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    candidates = data if isinstance(data, list) else [data]
    print(json.dumps({"assessments": [assess(c) for c in candidates]}, indent=2))

if __name__ == "__main__":
    main()
