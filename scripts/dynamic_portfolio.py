#!/usr/bin/env python3
"""Persistent, bounded APEX portfolio review. Never authorizes external execution.

This records research priorities and reservations only; no buyers, transactions,
provider permission, profits, or actual service capacity are inferred.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from scripts.business_model_intelligence import load_catalog, rank_models, pursuit_plan

def decide(models, capacity=None, active_ids=()):
    """Deterministic portfolio proposal with zero default admission."""
    ranked = rank_models(models, {
        "max_startup_cost": 4, "max_compliance_risk": 5,
        "min_automation": 6,
    })
    plan = pursuit_plan(ranked, pursue_limit=min(len(ranked), 100))
    candidates = plan.get("pursuits", [])
    if not isinstance(candidates, list) or not candidates:
        # Older pursuit_plan versions may use a different key; ranking is safe
        candidates = [m for m in ranked if m["eligible"]]
    active = set(active_ids)
    proposed = []
    budget = 0
    if isinstance(capacity, dict) and capacity.get("verified_for_preparation") is True:
        try:
            stamp = datetime.fromisoformat(capacity["attested_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
            minutes = capacity["free_preparation_minutes"]
            if (stamp.tzinfo is not None and 0 <= age < 86400
                and type(minutes) is int and 0 <= minutes <= 10080
                and capacity.get("haeven_priority_protected") is True
                and capacity.get("paid_obligations_protected") is True
                and capacity.get("settlement_reserve_protected") is True
                and isinstance(capacity.get("evidence_url"), str)
                and capacity["evidence_url"].startswith("https://")):
                budget = minutes
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
    for model in candidates:
        ident = model.get("id")
        if not ident or ident in active or any(x["model_id"] == ident for x in proposed):
            continue
        if budget < 30:
            break
        proposed.append({"model_id": ident, "reserved_preparation_minutes": 30,
                         "permission": "internal_research_and_draft_only"})
        budget -= 30
    return {
        "ranked_count": len(ranked), "eligible_count": sum(m["eligible"] for m in ranked),
        "active_ids_preserved": sorted(active), "proposed": proposed,
        "remaining_minutes": budget, "external_execution_authorized": False,
        "revenue_verified": False, "selection_only": True,
    }

def run(db_path=None, capacity_path=None):
    path = db_path or os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")
    db = sqlite3.connect(path, timeout=10)
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS apex_portfolio_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, observed_at TEXT NOT NULL,
            decision_json TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS apex_portfolio_active (
            model_id TEXT PRIMARY KEY, state TEXT NOT NULL,
            evidence_reference TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        active = [r[0] for r in db.execute(
            "SELECT model_id FROM apex_portfolio_active WHERE state IN ('active','funded','delivering')")]
        capacity = None
        # Local private capacity attestation is optional; no entry = research only.
        if capacity_path:
            p = Path(capacity_path)
            if p.is_file() and p.stat().st_size <= 32768:
                capacity = json.loads(p.read_text(encoding="utf-8"))
        result = decide(load_catalog()["models"], capacity, active)
        db.execute("INSERT INTO apex_portfolio_reviews(observed_at,decision_json) VALUES (?,?)",
                   (datetime.now(timezone.utc).isoformat(), json.dumps(result, sort_keys=True)))
        db.execute("""DELETE FROM apex_portfolio_reviews
                      WHERE id NOT IN (SELECT id FROM apex_portfolio_reviews
                                       ORDER BY id DESC LIMIT 500)""")
        db.commit()
        return result
    finally:
        db.close()

if __name__ == "__main__":
    print(json.dumps(run(capacity_path=os.getenv("APEX_CAPACITY_ATTESTATION_PATH"))))
