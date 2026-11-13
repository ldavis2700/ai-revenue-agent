#!/usr/bin/env python3
"""Generate a truthful owner-review financing packet from nonsensitive approved facts.

Local-only. No lender contact, inquiry, debt action or undisclosed data collection.
"""
import argparse
import json
from pathlib import Path
try:
    from scripts.business_financing_readiness import assess
except ModuleNotFoundError:
    from business_financing_readiness import assess

SECTIONS = (
    ("Business identity", ("legal_business_name", "entity_type", "state", "operating_since")),
    ("Business and market", ("industry", "business_description")),
    ("Requested capital", ("requested_amount", "use_of_funds")),
    ("Repayment inputs", ("annual_revenue", "annual_net_income", "existing_annual_debt_service")),
    ("Evidence index", ("source_documents",)),
)

def render(profile: dict) -> str:
    report = assess(profile)
    facts = report["verified_or_attested_facts"]
    lines = [
        "# Business financing readiness — OWNER REVIEW ONLY",
        "",
        "**Not a lender application or approval.** Do not submit without explicit owner authorization.",
        "All claims below are restricted to documented or owner-attested supplied facts.",
        "No missing value is estimated, imputed or made up.",
        "",
    ]
    for title, fields in SECTIONS:
        lines.extend(("## " + title, ""))
        for key in fields:
            fact = facts.get(key)
            if fact:
                val = fact["value"]
                # Avoid injection into markdown as markup. Sensitive data must not be included as input.
                safe = str(val).replace("\r", " ").replace("\n", " ")
                status = fact["evidence_status"]
                citation = ("; private reference: " + str(fact["source_reference"]).replace("\n"," ")) if status == "documented" else ""
                lines.append(f"- {key.replace('_', ' ').capitalize()}: {safe} [{status}{citation}]")
            else:
                lines.append(f"- {key.replace('_', ' ').capitalize()}: **MISSING / UNVERIFIED**")
        lines.append("")
    lines.extend((
        "## Underwriting and repayment review",
        "",
        "No approval probability, loan affordability, rate or creditworthiness has been inferred.",
        "Verify requested term, actual APR, payments, repayment sources, current debt, collateral,",
        "guarantees, eligibility and stress-tested cash flow before recommending borrowing.",
        "",
        "## Lender questions to resolve",
        "",
    ))
    lines.extend("- " + question for question in report["lender_questions"])
    lines.extend((
        "",
        "## Official starting points (research only; validate current terms)",
        "",
    ))
    lines.extend(f"- {name}: {url}" for name,url in report["programs_to_research_not_approvals"].items())
    lines.extend((
        "",
        "## Owner authorization gate",
        "",
        "No application, prequalification sharing private data, inquiry, fees, personal guarantee,",
        "signature, credit pull, account changes or acceptance of debt without specific approval.",
        "",
        f"Readiness: **{report['readiness']}**",
    ))
    return "\n".join(lines) + "\n"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile_json", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    profile = json.loads(a.profile_json.read_text(encoding="utf-8"))
    packet = render(profile)
    a.output.write_text(packet, encoding="utf-8")
    print("Created local review packet; no lender contacted.")

if __name__ == "__main__":
    main()
