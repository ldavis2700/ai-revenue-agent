#!/usr/bin/env python3
"""Continuously rank legitimate business models for APEX.

APEX should remain primed to favor the strongest risk-adjusted opportunities,
re-rank them as evidence changes, and pursue validated winners through separately
authorized execution systems. This module never weakens spend, contract,
production-deploy, consent, or compliance gates.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "config" / "business_models.json"
EXTENDED_CATALOG = ROOT / "config" / "business_models_expansion.json"

DEFAULT_WEIGHTS = {
    "speed_to_revenue": 0.23,
    "margin": 0.16,
    "startup_cost": 0.16,
    "automation": 0.15,
    "scalability": 0.12,
    "owner_effort": 0.12,
    "compliance_risk": 0.06,
}
LOW_IS_GOOD = {"startup_cost", "owner_effort", "compliance_risk"}
REQUIRED_FIELDS = {
    "id", "category", "name", "revenue_type", "speed_to_revenue", "margin",
    "startup_cost", "automation", "scalability", "owner_effort", "compliance_risk",
}

# These fields are derived exclusively from the auditable revenue ledger. Public
# CLI evidence may describe observations, but it cannot assert settled payments,
# recurring expansion, reuse, or earned mastery.
LEDGER_ONLY_EVIDENCE_KEYS = frozenset({
    "_ledger_verified", "verified_retention_receipts",
    "verified_expansion_receipts", "retained_recurring_value_cents",
    "expanded_value_delta_cents", "realized_recurring_net_cents",
    "realized_recurring_contribution_cents", "realized_recurring_cost_cents",
    "mastery", "receipt_lineage", "verified_reuse_receipts",
    "verified_reused_opportunities", "reuse_receipt_lineage",
    "verified_forecast_comparisons", "forecast_mean_absolute_error_cents",
    "forecast_mean_projected_contribution_cents",
})


def load_catalog(path: str | os.PathLike[str] = DEFAULT_CATALOG) -> dict[str, Any]:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload.get("models"), list):
        raise ValueError("catalog.models must be a list")

    # The default APEX universe is intentionally split into a stable core and an
    # extensible expansion file. Explicit custom catalogs remain self-contained.
    if path.resolve() == DEFAULT_CATALOG.resolve() and EXTENDED_CATALOG.exists():
        with open(EXTENDED_CATALOG, "r", encoding="utf-8") as handle:
            expansion = json.load(handle)
        if not isinstance(expansion.get("models"), list):
            raise ValueError("expansion.models must be a list")
        payload = {**payload, "models": [*payload["models"], *expansion["models"]]}

    seen: set[str] = set()
    for model in payload["models"]:
        missing = REQUIRED_FIELDS - model.keys()
        if missing:
            raise ValueError(f"{model.get('id', '<unknown>')} missing fields: {sorted(missing)}")
        if model["id"] in seen:
            raise ValueError(f"duplicate model id: {model['id']}")
        seen.add(model["id"])
        for key in DEFAULT_WEIGHTS:
            value = model[key]
            if not isinstance(value, (int, float)) or not 1 <= value <= 10:
                raise ValueError(f"{model['id']}.{key} must be between 1 and 10")
    return payload


def score_model(model: dict[str, Any], weights: dict[str, float] | None = None) -> float:
    weights = weights or DEFAULT_WEIGHTS
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("weights must sum to a positive number")
    score = 0.0
    for key, weight in weights.items():
        raw = float(model[key])
        normalized = (11.0 - raw) if key in LOW_IS_GOOD else raw
        score += normalized * weight
    return round((score / total_weight) * 10.0, 2)


def eligible(model: dict[str, Any], constraints: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    checks = (
        ("max_startup_cost", "startup_cost", lambda actual, target: actual > target, "startup_cost_above_limit"),
        ("max_owner_effort", "owner_effort", lambda actual, target: actual > target, "owner_effort_above_limit"),
        ("max_compliance_risk", "compliance_risk", lambda actual, target: actual > target, "compliance_risk_above_limit"),
        ("min_speed_to_revenue", "speed_to_revenue", lambda actual, target: actual < target, "speed_to_revenue_below_target"),
        ("min_automation", "automation", lambda actual, target: actual < target, "automation_below_target"),
    )
    for constraint, field, fails, reason in checks:
        target = constraints.get(constraint)
        if target is not None and fails(model[field], target):
            reasons.append(reason)
    return not reasons, reasons


def rank_models(models: list[dict[str, Any]], constraints: dict[str, Any] | None = None,
                weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    constraints = constraints or {}
    ranked = []
    for model in models:
        is_eligible, reasons = eligible(model, constraints)
        ranked.append({**model, "apex_score": score_model(model, weights), "eligible": is_eligible,
                       "constraint_reasons": reasons, "execution_gate": "candidate_only"})
    return sorted(ranked, key=lambda item: (item["eligible"], item["apex_score"]), reverse=True)


def portfolio(ranked: list[dict[str, Any]], limit: int = 10) -> dict[str, Any]:
    eligible_models = [m for m in ranked if m["eligible"]]
    selected: list[dict[str, Any]] = []
    represented: set[str] = set()
    for model in eligible_models:
        if model["category"] not in represented:
            selected.append(model)
            represented.add(model["category"])
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        ids = {m["id"] for m in selected}
        remaining = [m for m in eligible_models if m["id"] not in ids]
        selected.extend(remaining[: limit - len(selected)])
    return {"candidates": selected, "count": len(selected), "guardrails": {
        "recommendation_only": True, "automatic_spend": False, "automatic_contracts": False,
        "automatic_production_deploy": False, "automatic_unsolicited_outreach": False}}


def _finite_evidence_number(value: Any, field: str) -> float:
    """Reject booleans, NaN, and infinity before they can alter rankings."""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _parse_observed_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def evidence_freshness(evidence: dict[str, Any], now: datetime | None = None,
                       half_life_days: float = 30.0) -> float:
    """Decay old observations so yesterday's winner does not remain privileged forever."""
    # Preserve undated legacy observations, but never reward an explicitly
    # supplied timestamp that is invalid or lies in the future.
    if "observed_at" not in evidence:
        return 1.0
    observed_at = _parse_observed_at(evidence["observed_at"])
    if observed_at is None:
        return 0.0
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if observed_at > now:
        return 0.0
    age_days = (now - observed_at).total_seconds() / 86400.0
    half_life_days = max(
        1.0, _finite_evidence_number(half_life_days, "evidence_half_life_days"))
    return round(0.5 ** (age_days / half_life_days), 4)


def evidence_reliability(evidence: dict[str, Any]) -> float:
    """Temper small samples while keeping backward compatibility for uncounted legacy evidence."""
    if "sample_size" not in evidence:
        return 1.0
    sample_size = max(
        0.0,
        _finite_evidence_number(
            evidence.get("sample_size", 0) or 0, "sample_size"),
    )
    return round(min(1.0, sample_size / 20.0), 4)


def experiment_state(profit: float, conversion: float, effective_quality: float,
                     sample_size: float | None, economics_verified: bool) -> str:
    if effective_quality < 0.2:
        return "validate"
    if economics_verified and profit < 0 and effective_quality >= 0.5:
        return "deprioritize"
    if (
        economics_verified
        and profit > 0
        and conversion > 0
        and effective_quality >= 0.7
        and (sample_size is None or sample_size >= 10)
    ):
        return "scale_candidate"
    if economics_verified and profit > 0:
        return "continue_validation"
    return "validate"


def verified_forecast_calibration(evidence: dict[str, Any],
                                  ledger_verified: bool) -> dict[str, Any]:
    """Return a bounded decision signal from receipt-verified forecast results."""
    if not ledger_verified:
        return {
            "comparison_count": 0,
            "relative_error": None,
            "confidence": 0.0,
        }
    count = max(0, int(_finite_evidence_number(
        evidence.get("verified_forecast_comparisons", 0) or 0,
        "verified_forecast_comparisons")))
    absolute_error = max(0.0, _finite_evidence_number(
        evidence.get("forecast_mean_absolute_error_cents", 0) or 0,
        "forecast_mean_absolute_error_cents"))
    projected = max(0.0, _finite_evidence_number(
        evidence.get("forecast_mean_projected_contribution_cents", 0) or 0,
        "forecast_mean_projected_contribution_cents"))
    if count == 0 or projected <= 0:
        return {
            "comparison_count": count,
            "relative_error": None,
            "confidence": 0.0,
        }
    relative_error = absolute_error / projected
    calibration = max(0.0, 1.0 - min(1.0, relative_error))
    sample_reliability = min(1.0, count / 10.0)
    return {
        "comparison_count": count,
        "relative_error": round(relative_error, 4),
        "confidence": round(calibration * sample_reliability, 4),
    }


def pursuit_plan(ranked: list[dict[str, Any]], active: dict[str, dict[str, Any]] | None = None,
                 pursue_limit: int = 3, now: datetime | None = None,
                 evidence_half_life_days: float = 30.0) -> dict[str, Any]:
    """Turn rankings into a standing, evidence-driven pursuit posture.

    Market observations can reprioritize validation without changing hard safety
    gates, but only receipt-backed ledger economics may produce profit or scale
    states. Supported evidence keys: observed_revenue, observed_cost,
    conversion_rate, evidence_quality (0..1), observed_at (ISO-8601), and
    sample_size. Unverified revenue/cost remain explicitly labeled claims. Mission
    Control may also add receipt-backed recurring retention, expansion, realized
    contribution, cross-opportunity reusable-IP reuse, and mastery fields marked
    with its private ledger-verification flag; unverified callers receive no
    maturity, recurring-growth, or reuse bonus.
    """
    active = active or {}
    enriched = []
    for model in ranked:
        evidence = active.get(model["id"], {})
        claimed_revenue = max(
            0.0,
            _finite_evidence_number(
                evidence.get("observed_revenue", 0) or 0,
                "observed_revenue",
            ),
        )
        claimed_cost = max(
            0.0,
            _finite_evidence_number(
                evidence.get("observed_cost", 0) or 0,
                "observed_cost",
            ),
        )
        conversion = min(
            1.0,
            max(
                0.0,
                _finite_evidence_number(
                    evidence.get("conversion_rate", 0) or 0,
                    "conversion_rate",
                ),
            ),
        )
        quality = min(
            1.0,
            max(
                0.0,
                _finite_evidence_number(
                    evidence.get("evidence_quality", 0) or 0,
                    "evidence_quality",
                ),
            ),
        )
        freshness = evidence_freshness(evidence, now, evidence_half_life_days)
        reliability = evidence_reliability(evidence)
        effective_quality = round(quality * freshness * reliability, 4)
        ledger_verified = evidence.get("_ledger_verified") is True
        revenue = claimed_revenue if ledger_verified else 0.0
        cost = claimed_cost if ledger_verified else 0.0
        profit = revenue - cost
        retention_receipts = (
            max(0, int(evidence.get("verified_retention_receipts", 0) or 0))
            if ledger_verified else 0)
        expansion_receipts = (
            max(0, int(evidence.get("verified_expansion_receipts", 0) or 0))
            if ledger_verified else 0)
        reuse_receipts = (
            max(0, int(evidence.get("verified_reuse_receipts", 0) or 0))
            if ledger_verified else 0)
        reused_opportunities = (
            max(0, int(evidence.get(
                "verified_reused_opportunities", 0) or 0))
            if ledger_verified else 0)
        retained_value_cents = (
            max(0, int(evidence.get("retained_recurring_value_cents", 0) or 0))
            if ledger_verified else 0)
        expanded_value_delta_cents = (
            max(0, int(evidence.get("expanded_value_delta_cents", 0) or 0))
            if ledger_verified else 0)
        mastery = (
            str(evidence.get("mastery") or "learned")
            if ledger_verified else "learned")
        forecast_calibration = verified_forecast_calibration(
            evidence, ledger_verified)
        evidence_bonus = effective_quality * min(
            8.0, max(-8.0, profit / 100.0 + conversion * 5.0))
        recurring_growth_bonus = effective_quality * min(
            3.0, retention_receipts * 0.5 + expansion_receipts * 0.75)
        verified_reuse_bonus = effective_quality * min(
            2.0, reuse_receipts * 0.5 + reused_opportunities * 0.75)
        forecast_calibration_bonus = (
            effective_quality * forecast_calibration["confidence"]
            if ledger_verified and profit > 0 else 0.0)
        pursuit_score = round(
            model["apex_score"] + evidence_bonus + recurring_growth_bonus
            + verified_reuse_bonus + forecast_calibration_bonus, 2)
        sample_size = (
            None
            if "sample_size" not in evidence
            else max(
                0.0,
                _finite_evidence_number(
                    evidence.get("sample_size", 0) or 0, "sample_size"),
            )
        )
        enriched.append({
            **model,
            "pursuit_score": pursuit_score,
            "observed_profit": round(profit, 2),
            "claimed_observed_revenue": round(claimed_revenue, 2),
            "claimed_observed_cost": round(claimed_cost, 2),
            "economics_verified": ledger_verified,
            "evidence_quality": quality,
            "evidence_freshness": freshness,
            "evidence_reliability": reliability,
            "effective_evidence_quality": effective_quality,
            "ledger_verified_recurring_evidence": ledger_verified,
            "verified_retention_receipts": retention_receipts,
            "verified_expansion_receipts": expansion_receipts,
            "verified_reuse_receipts": reuse_receipts,
            "verified_reused_opportunities": reused_opportunities,
            "ledger_verified_reuse_evidence":
                ledger_verified and reuse_receipts > 0,
            "retained_recurring_value_cents": retained_value_cents,
            "expanded_value_delta_cents": expanded_value_delta_cents,
            "mastery": mastery,
            "verified_forecast_calibration": forecast_calibration,
            "forecast_calibration_bonus": round(
                forecast_calibration_bonus, 4),
            "experiment_state": experiment_state(
                profit, conversion, effective_quality, sample_size,
                ledger_verified),
        })
    enriched.sort(key=lambda item: (item["eligible"], item["pursuit_score"]), reverse=True)
    pursue = [m for m in enriched if m["eligible"]][:max(1, pursue_limit)]
    return {
        "mode": "continuous_opportunity_optimization",
        "objective": "maximize durable risk-adjusted owner wealth",
        "pursue": pursue,
        "standing_directives": [
            "continuously compare active models with newly discovered legitimate opportunities",
            "favor validated revenue, profit, recurring economics, automation, scalability, and low owner effort",
            "discount stale or weak evidence so historical winners must keep earning priority",
            "run bounded validation before materially scaling uncertain opportunities",
            "increase attention to winners and retire or redesign persistent underperformers",
            "preserve customer trust, privacy, platform rules, law, and long-term business value",
            "escalate actions requiring spend, contracts, production deployment, or other owner-gated authority",
        ],
    }


def parse_constraints(args: argparse.Namespace) -> dict[str, Any]:
    return {key: value for key, value in {
        "max_startup_cost": args.max_startup_cost, "max_owner_effort": args.max_owner_effort,
        "max_compliance_risk": args.max_compliance_risk, "min_speed_to_revenue": args.min_speed_to_revenue,
        "min_automation": args.min_automation}.items() if value is not None}


def sanitize_public_evidence(payload: Any) -> dict[str, dict[str, Any]]:
    """Remove ledger-derived assertions from untrusted CLI evidence."""
    if not isinstance(payload, dict):
        raise ValueError("evidence JSON must be an object keyed by model id")
    sanitized: dict[str, dict[str, Any]] = {}
    for model_id, evidence in payload.items():
        if not isinstance(model_id, str) or not isinstance(evidence, dict):
            raise ValueError("each evidence entry must be an object keyed by model id")
        sanitized[model_id] = {
            key: value for key, value in evidence.items()
            if key not in LEDGER_ONLY_EVIDENCE_KEYS
        }
    return sanitized


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank and prime APEX business-model opportunities")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG)); parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--pursue-limit", type=int, default=3); parser.add_argument("--evidence-json")
    parser.add_argument("--evidence-half-life-days", type=float, default=30.0)
    parser.add_argument("--max-startup-cost", type=int, default=3); parser.add_argument("--max-owner-effort", type=int, default=5)
    parser.add_argument("--max-compliance-risk", type=int, default=4); parser.add_argument("--min-speed-to-revenue", type=int, default=5)
    parser.add_argument("--min-automation", type=int, default=6); args = parser.parse_args()
    catalog = load_catalog(args.catalog); constraints = parse_constraints(args)
    ranked = rank_models(catalog["models"], constraints); output = portfolio(ranked, max(1, args.limit))
    evidence = sanitize_public_evidence(
        json.loads(args.evidence_json)) if args.evidence_json else {}
    output.update({"schema_version": catalog.get("schema_version", 1), "catalog_size": len(catalog["models"]),
                   "constraints": constraints, "top_ranked": ranked[:max(1, args.limit)],
                   "pursuit_plan": pursuit_plan(ranked, evidence, args.pursue_limit,
                                                evidence_half_life_days=args.evidence_half_life_days),
                   "hard_exclusions": catalog.get("hard_exclusions", [])})
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
