#!/usr/bin/env python3
"""Select a measured champion and bounded challenger from APEX business-model candidates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

VALIDATED_STATES = {"continue_validation", "scale_candidate"}
RETIRED_STATES = {"deprioritize"}


def compare_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a recommendation-only champion/challenger comparison.

    A champion must have measured evidence and a non-retired experiment state. A challenger
    is the highest-scoring distinct eligible candidate. This never authorizes spend, outreach,
    contracts, charging, deployment, or customer-system changes.
    """
    eligible = [c for c in candidates if c.get("eligible", True) and c.get("experiment_state") not in RETIRED_STATES]
    measured = [
        c for c in eligible
        if c.get("experiment_state") in VALIDATED_STATES and float(c.get("effective_evidence_quality", 0) or 0) > 0
    ]
    champion = max(measured, key=lambda c: float(c.get("pursuit_score", 0) or 0), default=None)

    challenger_pool = [c for c in eligible if champion is None or c.get("id") != champion.get("id")]
    challenger = max(challenger_pool, key=lambda c: float(c.get("pursuit_score", 0) or 0), default=None)

    if champion is None and challenger is None:
        posture = "no_viable_candidate"
        action = "discover_or_repair_candidates"
    elif champion is None:
        posture = "challenger_only"
        action = "validate_challenger"
    elif challenger is None:
        posture = "champion_only"
        action = "continue_measuring_champion"
    else:
        gap = round(float(challenger.get("pursuit_score", 0)) - float(champion.get("pursuit_score", 0)), 2)
        if gap >= 2.0:
            posture = "challenger_advantage"
            action = "run_bounded_head_to_head_validation"
        elif gap <= -2.0 and champion.get("experiment_state") == "scale_candidate":
            posture = "champion_advantage"
            action = "protect_winner_and_probe_challenger"
        else:
            posture = "competitive"
            action = "run_bounded_head_to_head_validation"

    result = {
        "posture": posture,
        "recommended_action": action,
        "champion": champion,
        "challenger": challenger,
        "execution_gate": "recommendation_only",
        "guardrails": {
            "automatic_spend": False,
            "automatic_outreach": False,
            "automatic_contracts": False,
            "automatic_charging": False,
            "automatic_production_deploy": False,
        },
    }
    if champion is not None and challenger is not None:
        result["challenger_minus_champion_score"] = round(
            float(challenger.get("pursuit_score", 0)) - float(champion.get("pursuit_score", 0)), 2)
    return result


def candidates_from_intelligence(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the evidence-enriched pursuit candidates from an intelligence snapshot."""
    pursuit = payload.get("pursuit_plan", {}).get("pursue")
    if isinstance(pursuit, list):
        return pursuit
    candidates = payload.get("candidates")
    return candidates if isinstance(candidates, list) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare APEX champion and challenger opportunities")
    parser.add_argument("--intelligence-json", required=True, help="Path to a business-model intelligence snapshot")
    args = parser.parse_args()
    payload = json.loads(Path(args.intelligence_json).read_text(encoding="utf-8"))
    print(json.dumps(compare_candidates(candidates_from_intelligence(payload)), indent=2))


if __name__ == "__main__":
    main()
