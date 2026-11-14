#!/usr/bin/env python3
"""Generate a truthful owner-review financing packet from nonsensitive approved facts.

Local-only. No lender contact, inquiry, debt action or undisclosed data collection.
"""
import argparse
import html
import json
from math import expm1, isfinite, log1p
from pathlib import Path
try:
    from scripts.business_financing_readiness import assess, write_private_output
except ModuleNotFoundError:
    from business_financing_readiness import assess, write_private_output

SECTIONS = (
    ("Business identity", ("legal_business_name", "entity_type", "state", "operating_since")),
    ("Business and market", ("industry", "business_description")),
    ("Requested capital", ("requested_amount", "use_of_funds")),
    ("Repayment inputs", ("annual_revenue", "annual_net_income", "annual_cash_available_for_debt_service",
                          "existing_annual_debt_service", "annual_interest_rate_pct",
                          "term_months", "upfront_fees")),
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


def markdown_literal(value: object) -> str:
    """Render supplied business facts and private source pointers as inert text.

    A private owner-review packet must not turn untrusted input into images,
    links, headings or raw HTML when opened in a Markdown preview.
    """
    raw = " ".join(str(value).splitlines())
    raw = "".join(
        " " if (ord(char) < 32 or 0x7f <= ord(char) <= 0x9f
                or char in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
        else char for char in raw
    )
    escaped_html = html.escape(raw, quote=True)
    markdown_special = set("\\`*_{}[]()#+-.!|>")
    return "".join("\\" + char if char in markdown_special else char
                   for char in escaped_html)


def repayment_lines(profile: dict) -> list[str]:
    """Conservative scenario only when all six inputs have actual evidence.

    A quoted nominal rate is not the same as a disclosed APR. Never invent
    a fee, debt balance, cash-flow projection, or safe borrowing estimate.
    Refuse unrepresentable figures rather than print Infinity or NaN.
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
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise ValueError("Repayment figures must all be finite numbers")
    try:
        principal, annual_rate_pct, months, fees, cash, existing = (float(v) for v in values)
    except (OverflowError, ValueError):
        raise ValueError("Repayment figures must all be finite numbers") from None
    if not all(isfinite(v) for v in (principal, annual_rate_pct, months, fees, cash, existing)):
        raise ValueError("Repayment figures must all be finite numbers")
    if (principal <= 0 or not 0 <= annual_rate_pct <= 100
            or not isinstance(values[2], int) or not 1 <= months <= 360
            or fees < 0 or existing < 0):
        raise ValueError("Invalid principal, rate, term, fees or existing debt service")

    def finite(value: float) -> float:
        if not isfinite(value):
            raise ValueError("Repayment scenario cannot be calculated with finite values")
        return value

    monthly_rate = annual_rate_pct / 1200
    if monthly_rate == 0:
        payment = principal / months
    else:
        # Stable for tiny rates, unlike subtracting a number close to 1.
        payment = principal * monthly_rate / (-expm1(-months * log1p(monthly_rate)))
    payment = finite(payment)
    combined_service = finite(finite(payment * 12) + existing)
    total_paid = finite(finite(payment * months) + fees)
    stress_cash = finite(cash - 0.20 * abs(cash))
    base_dscr = finite(cash / combined_service)
    stress_dscr = finite(stress_cash / combined_service)
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
            # The readiness assessor tracks core company facts, not optional
            # scenario terms. Show supplied rate/term/fee provenance directly,
            # but only when the owner explicitly labels the evidence.
            if fact is None and key in ("annual_interest_rate_pct", "term_months", "upfront_fees"):
                item = profile.get("evidence", {}).get(key, {})
                value = profile.get(key)
                if (isinstance(item, dict) and value is not None
                        and item.get("status") in ("documented", "owner_attested")
                        and (item["status"] == "owner_attested" or item.get("source"))):
                    fact = {"value": value, "evidence_status": item["status"],
                            "source_reference": item.get("source", "")}
            if fact:
                val = fact["value"]
                # Sensitive identifiers remain prohibited upstream; escape even nonsensitive
                # supplied facts so Markdown previews cannot load external images/links.
                safe = markdown_literal(val)
                status = fact["evidence_status"]
                citation = ("; private reference: " + markdown_literal(fact["source_reference"])) if status == "documented" else ""
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
