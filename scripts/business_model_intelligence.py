#!/usr/bin/env python3
"""Rank legitimate online business models for APEX.

The seed catalog is intentionally extensible. New candidates can be supplied as
JSON, scored with the same framework, and kept behind approval/guardrail gates.
This module recommends models; it does not spend money, enter contracts, contact
prospects, or deploy production changes.
"""
from __future__ import annotations

import argparse
import json
import os
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
    max_cost = constraints.get("max_startup_cost")
    if max_cost is not None and model["startup_cost"] > max_cost:
        reasons.append("startup_cost_above_limit")
    max_owner_effort = constraints.get("max_owner_effort")
    if max_owner_effort is not None and model["owner_effort"] > max_owner_effort:
        reasons.append("owner_effort_above_limit")
    max_risk = constraints.get("max_compliance_risk")
    if max_risk is not None and model["compliance_risk"] > max_risk:
        reasons.append("compliance_risk_above_limit")
    min_speed = constraints.get("min_speed_to_revenue")
    if min_speed is not None and model["speed_to_revenue"] < min_speed:
        reasons.append("speed_to_revenue_below_target")
    min_automation = constraints.get("min_automation")
    if min_automation is not None and model["automation"] < min_automation:
        reasons.append("automation_below_target")
    return not reasons, reasons


def rank_models(models: list[dict[str, Any]], constraints: dict[str, Any] | None = None,
                weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    constraints = constraints or {}
    ranked = []
    for model in models:
        is_eligible, reasons = eligible(model, constraints)
        ranked.append({
            **model,
            "apex_score": score_model(model, weights),
            "eligible": is_eligible,
            "constraint_reasons": reasons,
            "execution_gate": "candidate_only",
        })
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
    return {
        "candidates": selected,
        "count": len(selected),
        "guardrails": {
            "recommendation_only": True,
            "automatic_spend": False,
            "automatic_contracts": False,
            "automatic_production_deploy": False,
            "automatic_unsolicited_outreach": False,
        },
    }


def parse_constraints(args: argparse.Namespace) -> dict[str, Any]:
    return {key: value for key, value in {
        "max_startup_cost": args.max_startup_cost,
        "max_owner_effort": args.max_owner_effort,
        "max_compliance_risk": args.max_compliance_risk,
        "min_speed_to_revenue": args.min_speed_to_revenue,
        "min_automation": args.min_automation,
    }.items() if value is not None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank APEX online business-model archetypes")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-startup-cost", type=int, default=3)
    parser.add_argument("--max-owner-effort", type=int, default=5)
    parser.add_argument("--max-compliance-risk", type=int, default=4)
    parser.add_argument("--min-speed-to-revenue", type=int, default=5)
    parser.add_argument("--min-automation", type=int, default=6)
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    constraints = parse_constraints(args)
    ranked = rank_models(catalog["models"], constraints)
    output = portfolio(ranked, max(1, args.limit))
    output.update({
        "schema_version": catalog.get("schema_version", 1),
        "catalog_size": len(catalog["models"]),
        "constraints": constraints,
        "top_ranked": ranked[: max(1, args.limit)],
        "hard_exclusions": catalog.get("hard_exclusions", []),
    })
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
