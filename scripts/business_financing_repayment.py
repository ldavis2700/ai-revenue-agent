"""Illustrative-only repayment model; never a lender quote or credit decision.

No network, data storage, lender applications, or invented financial inputs.
Only verified-or-owner-attested facts from the readiness assessor may be used.
"""
from __future__ import annotations

from math import expm1, isfinite, log1p


def _number(value: object, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + " must be a finite numeric assumption")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise ValueError(label + " must be a finite numeric assumption") from None
    if not isfinite(number) or number < minimum:
        raise ValueError(label + " must be finite and at least " + str(minimum))
    return number


def _finite_result(value: float, label: str) -> float:
    """Never emit infinity or NaN as an illustrative financing result."""
    if not isfinite(value):
        raise ValueError(label + " cannot be calculated with finite values")
    return value


def analyze_repayment(profile: dict, facts: dict) -> dict:
    """Compute an owner-specified fixed-rate amortization scenario, not eligibility."""
    scenario = profile.get("repayment_scenario")
    if scenario is None:
        return {"status": "not_modeled", "reason": "No owner-specified rate and repayment term"}
    if not isinstance(scenario, dict):
        raise ValueError("repayment_scenario must be an object")
    rate = _number(scenario.get("assumed_nominal_annual_rate_pct"),
                   "assumed_nominal_annual_rate_pct")
    if rate > 100:
        raise ValueError("Assumed nominal rate must not exceed 100%")
    months = scenario.get("assumed_term_months")
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 360:
        raise ValueError("assumed_term_months must be an integer from 1 to 360")
    amount_fact = facts.get("requested_amount")
    if amount_fact is None:
        return {"status": "insufficient_evidence",
                "missing_or_unsubstantiated": ["requested_amount"],
                "reason": "No evidence-backed principal; no repayment estimate generated"}
    principal = _number(amount_fact["value"], "requested_amount", minimum=0.01)
    monthly_rate = rate / 1200
    if monthly_rate == 0:
        monthly_payment = principal / months
    else:
        # Numerically stable for small positive rates and long terms.
        monthly_payment = principal * monthly_rate / (-expm1(
            -months * log1p(monthly_rate)))
    monthly_payment = _finite_result(monthly_payment, "Monthly payment")
    total_installments = _finite_result(monthly_payment * months, "Total installments")
    annual_new_service = _finite_result(monthly_payment * 12, "Annual debt service")
    result = {
        "status": "illustrative_only",
        "owner_supplied_assumptions": {
            "nominal_annual_interest_rate_pct": rate,
            "term_months": months,
            "principal": principal,
        },
        "estimated_monthly_installment": round(monthly_payment, 2),
        "estimated_annualized_new_debt_service": round(annual_new_service, 2),
        "estimated_total_installments_excluding_fees": round(total_installments, 2),
        "estimated_total_interest_excluding_fees": round(
            max(0.0, total_installments - principal), 2),
        "coverage": {"status": "not_calculated",
                     "reason": "Documented/attested debt-service cash flow and existing debt service are required"},
        "missing_loan_costs": ["origination/guaranty fees", "closing costs",
                               "collateral and guarantee terms", "variable-rate changes"],
        "warning": ("Hypothetical fixed-rate amortization only, not a lender APR, offer, "
                    "approval, eligibility result, or complete borrowing cost."),
    }
    cash_fact = facts.get("annual_cash_available_for_debt_service")
    old_debt_fact = facts.get("existing_annual_debt_service")
    if cash_fact is not None and old_debt_fact is not None:
        cash = _number(cash_fact["value"], "annual_cash_available_for_debt_service",
                       minimum=-1e15)
        old_debt = _number(old_debt_fact["value"], "existing_annual_debt_service")
        total_annual_service = _finite_result(
            old_debt + annual_new_service, "Total annual debt service")
        # A 20% downside should never make negative cash flow appear better.
        stressed_cash = _finite_result(
            cash - abs(cash) * 0.2, "Downside cash flow")
        result["coverage"] = {
            "status": "illustrative_cash_flow_proxy_not_lender_dscr",
            "annual_cash_available_for_debt_service": cash,
            "existing_annual_debt_service": old_debt,
            "total_annualized_debt_service": round(total_annual_service, 2),
            "base_coverage_ratio": round(cash / total_annual_service, 3),
            "downside_20pct_cash_flow": round(stressed_cash, 2),
            "downside_coverage_ratio": round(stressed_cash / total_annual_service, 3),
            "warning": ("Cash-flow coverage is an input-dependent proxy; not an "
                        "underwriting DSCR, eligibility score, or repayment guarantee."),
        }
    return result
