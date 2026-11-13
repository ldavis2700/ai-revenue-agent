#!/usr/bin/env python3
"""Offline, evidence-first small-business financing readiness assistant.

No lender submissions, credit pulls, banking access, borrowing, or network calls.
Input must be owner-authorized and must not contain SSNs, account numbers or DOBs.
"""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path

REQUIRED = (
    "legal_business_name", "entity_type", "state", "industry",
    "business_description", "operating_since", "use_of_funds",
    "requested_amount", "annual_revenue", "annual_net_income",
    "existing_annual_debt_service", "source_documents",
)
SENSITIVE = {"ssn", "social_security_number", "ein", "tax_id", "dob",
             "date_of_birth", "bank_account", "routing_number", "password",
             "api_key", "credit_card", "passport_number"}
OFFICIAL_SOURCES = {
    "SBA 7(a)": "https://www.sba.gov/loans/7a-loans/",
    "SBA microloans": "https://www.sba.gov/loans/microloans/",
    "SBA Lender Match": "https://www.sba.gov/loans/lender-match/",
}
ALLOWED_STATUS = {"documented", "owner_attested", "missing"}

def assess(profile: dict) -> dict:
    if not isinstance(profile, dict):
        raise ValueError("Input profile must be a JSON object")
    prohibited = sorted(set(k.lower() for k in profile) & SENSITIVE)
    if prohibited:
        raise ValueError("Sensitive fields must not be provided: " + ", ".join(prohibited))
    evidence = profile.get("evidence", {})
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    gaps, facts = [], {}
    for field in REQUIRED:
        val = profile.get(field)
        item = evidence.get(field, {})
        if not isinstance(item, dict):
            item = {}
        status = item.get("status", "missing")
        if status not in ALLOWED_STATUS:
            raise ValueError("Invalid evidence status for " + field)
        source = item.get("source", "")
        if not val or status == "missing" or (status == "documented" and not source):
            gaps.append(field)
        else:
            facts[field] = {"value": val, "evidence_status": status,
                            "source_reference": source if status == "documented" else ""}
    amount = profile.get("requested_amount")
    if amount is not None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("requested_amount must be a positive number")
    for field in ("annual_revenue", "annual_net_income", "existing_annual_debt_service"):
        v = profile.get(field)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int,float))):
            raise ValueError(field + " must be numeric")
    # No synthetic bankability or approval score: lender underwriting is specific.
    readiness = "ready_for_owner_review" if not gaps else "evidence_incomplete"
    return {
        "generated_on": date.today().isoformat(),
        "readiness": readiness,
        "company_name": facts.get("legal_business_name", {}).get("value", "Unverified"),
        "verified_or_attested_facts": facts,
        "missing_or_unsubstantiated": gaps,
        "lender_questions": [
            "Is the business/owner eligible under current program and lender policy?",
            "What revenue, credit, operating history and repayment evidence is required?",
            "What are APR, total fees, collateral, guarantee, repayment and default terms?",
            "Is prequalification a soft inquiry? Obtain owner consent before any credit pull.",
            "What is the permitted use of proceeds and are there prepayment penalties?",
        ],
        "programs_to_research_not_approvals": OFFICIAL_SOURCES,
        "next_action": (
            "Owner: review facts, proposed debt amount, repayment capacity, and each application."
            if readiness == "ready_for_owner_review"
            else "Collect and verify missing evidence before presenting to any lender."
        ),
        "prohibited_actions": [
            "Invent revenue, customers, business age, credit, collateral or financial statements",
            "Use synthetic identities, shelf corporations, tradelines or false addresses",
            "Send applications or personal information without specific informed owner approval",
            "Trigger a hard credit check, pay fees, authorize a guarantee or accept a loan",
            "Store unredacted sensitive identity, tax or banking data in repository/logs",
        ],
        "note": "Preparation only. No loan eligibility, approval, rate, or availability is asserted.",
    }

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_json", type=Path, help="Local, approved, non-sensitive input")
    parser.add_argument("--output", type=Path, help="Optional local output path")
    args = parser.parse_args()
    report = assess(json.loads(args.profile_json.read_text(encoding="utf-8")))
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)

if __name__ == "__main__":
    main()
