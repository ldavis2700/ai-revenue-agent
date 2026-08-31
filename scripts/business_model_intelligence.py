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
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "config" / "business_models.json"

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


def load_catalog(path: str | os.PathLike[str] = DEFAULT_CATALOG) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload.get("models"), list):
        raise ValueError("catalog.models must be a list")
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
    observed_at = _parse_observed_at(evidence.get("observed_at"))
    if observed_at is None:
        return 1.0
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_days = max(0.0, (now - observed_at).total_seconds() / 86400.0)
    half_life_days = max(1.0, float(half_life_days))
    return round(0.5 ** (age_days / half_life_days), 4)


def evidence_reliability(evidence: dict[str, Any]) -> float:
    """Temper small samples while keeping backward compatibility for uncounted legacy evidence."""
    if "sample_size" not in evidence:
        return 1.0
    sample_size = max(0.0, float(evidence.get("sample_size", 0) or 0))
    return round(min(1.0, sample_size / 20.0), 4)


def experiment_state(profit: float, conversion: float, effective_quality: float,
                     sample_size: float | None) -> str:
    if effective_quality < 0.2:
        return "validate"
    if profit < 0 and effective_quality >= 0.5:
        return "deprioritize"
    if profit > 0 and conversion > 0 and effective_quality >= 0.7 and (sample_size is None or sample_size >= 10):
        return "scale_candidate"
    if profit > 0:
        return "continue_validation"
    return "validate"


def pursuit_plan(ranked: list[dict[str, Any]], active: dict[str, dict[str, Any]] | None = None,
                 pursue_limit: int = 3, now: datetime | None = None,
                 evidence_half_life_days: float = 30.0) -> dict[str, Any]:
    """Turn rankings into a standing, evidence-driven pursuit posture.

    Observed economics can promote/demote models without changing hard safety gates.
    Supported evidence keys: observed_revenue, observed_cost, conversion_rate,
    evidence_quality (0..1), observed_at (ISO-8601), and sample_size.
    """
    active = active or {}
    enriched = []
    for model in ranked:
        evidence = active.get(model["id"], {})
        revenue = max(0.0, float(evidence.get("observed_revenue", 0) or 0))
        cost = max(0.0, float(evidence.get("observed_cost", 0) or 0))
        conversion = min(1.0, max(0.0, float(evidence.get("conversion_rate", 0) or 0)))
        quality = min(1.0, max(0.0, float(evidence.get("evidence_quality", 0) or 0)))
        freshness = evidence_freshness(evidence, now, evidence_half_life_days)
        reliability = evidence_reliability(evidence)
        effective_quality = round(quality * freshness * reliability, 4)
        profit = revenue - cost
        evidence_bonus = effective_quality * min(8.0, max(-8.0, profit / 100.0 + conversion * 5.0))
        pursuit_score = round(model["apex_score"] + evidence_bonus, 2)
        sample_size = None if "sample_size" not in evidence else max(0.0, float(evidence.get("sample_size", 0) or 0))
        enriched.append({
            **model,
            "pursuit_score": pursuit_score,
            "observed_profit": round(profit, 2),
            "evidence_quality": quality,
            "evidence_freshness": freshness,
            "evidence_reliability": reliability,
            "effective_evidence_quality": effective_quality,
            "experiment_state": experiment_state(profit, conversion, effective_quality, sample_size),
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
    evidence = json.loads(args.evidence_json) if args.evidence_json else {}
    output.update({"schema_version": catalog.get("schema_version", 1), "catalog_size": len(catalog["models"]),
                   "constraints": constraints, "top_ranked": ranked[:max(1, args.limit)],
                   "pursuit_plan": pursuit_plan(ranked, evidence, args.pursue_limit,
                                                evidence_half_life_days=args.evidence_half_life_days),
                   "hard_exclusions": catalog.get("hard_exclusions", [])})
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
