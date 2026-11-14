#!/usr/bin/env python3
"""Generate a truthful owner-review financing packet from nonsensitive approved facts.

Local-only. No lender contact, inquiry, debt action or undisclosed data collection.
"""
import argparse
import json
from math import isfinite
from pathlib import Path
try:
    from scripts.business_financing_readiness import assess, write_private_output
except ModuleNotFoundError:
    from business_financing_readiness import assess, write_private_output

SECTIONS = (
    ("Business identity", ("legal_business_name", "entity_type", "state", "operating_since")),
    ("Business and market", ("industry", "business_description")),
    ("Requested capital", ("requested_amount", "use_of_funds")),
    ("Repayment inputs", ("annual_revenue", "annual_net_income", "existing_annual_debt_service")),
    ("Evidence index", ("source_documents",)),
)

REPAYMENT_INPUTS = (
    "requested_amount",
    "annual_interest_rate_pct",
    "term_months",
    "upfront_fees",
    "annual_cash_available_for_debt_service",
    "existing_annual_debt_service",
)

def repayment_lines(profile: dict) -> list[str]:
    """Conservative scenario only when all six inputs have actual evidence.

    A quoted nominal rate is not the same as disclosed APR. Never create a
    fictitious rate, term, fee, zero debt balance or cash-flow forecast.
    """
    evidence = profile.get("evidence", {})
    missing = [
        key for key in REPAYMENT_INPUTS
        if key not in profile or not isinstance(evidence.get(key), dict)
        or evidence[key].get("status") != "documented"
        or not evidence[key].get("source")
    ]
    if missing:
        return ["**CANNOT ASSESS:** Missing documented repayment inputs: "
                + ", ".join(missing) + ".", "No debt-service or affordability estimate generated."]
    values = [profile[k] for k in REPAYMENT_INPUTS]
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not isfinite(v) for v in values):
        raise ValueError("Repayment figures must all be finite numbers")
    principal, annual_rate_pct, months, fees, cash, existing = values
    if (principal <= 0 or not 0 <= annual_rate_pct <= 100
            or not isinstance(months, int) or not 1 <= months <= 360
            or fees < 0 or existing < 0):
        raise ValueError("Invalid principal, rate, term, fees or existing debt service")
    monthly_rate = annual_rate_pct / 1200
    payment = (principal / months if monthly_rate == 0 else
               principal * monthly_rate / (1 - (1 + monthly_rate) ** (-months)))
    combined_service = payment * 12 + existing
    total_paid = payment * months + fees
    stress_cash = cash - 0.20 * abs(cash)
    base_dscr = cash / combined_service
    stress_dscr = stress_cash / combined_service
    return [
        "**Illustrative only: documented borrower inputs, not a lender quote or approval.**",
        f"New-loan scheduled monthly payment: ${payment:,.2f}; existing annual debt service: ${existing:,.2f}.",
        f"Illustrative lifetime loan payments plus known upfront fees: ${total_paid:,.2f}; "
        f"of which upfront fees are ${fees:,.2f}. Other costs remain unresolved.",
        f"Base debt-service coverage: {base_dscr:.2f}x; conservative cash-flow downside "
        f"(-20% of absolute cash amount): {stress_dscr:.2f}x.",
        "The payment approximation uses the documented nominal annual rate, not an APR disclosure. "
        "Ask the lender for actual APR, amortization, servicing fees, default terms, "
        "personal guarantees and collateral. These ratios are not underwriting decisions.",
    ]

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
    ))
    lines.extend(repayment_lines(profile))
    lines.extend((
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
    write_private_output(a.output, packet)
    print("Created local review packet; no lender contacted.")

if __name__ == "__main__":
    main()
