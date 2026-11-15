import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from scripts.dynamic_portfolio import decide, run

MODELS = [
    {"id": "one", "category": "services", "name": "One", "revenue_type": "project",
     "speed_to_revenue": 9, "margin": 9, "startup_cost": 1, "automation": 9,
     "scalability": 8, "owner_effort": 2, "compliance_risk": 1},
    {"id": "two", "category": "services", "name": "Two", "revenue_type": "project",
     "speed_to_revenue": 8, "margin": 8, "startup_cost": 1, "automation": 9,
     "scalability": 8, "owner_effort": 2, "compliance_risk": 1},
    {"id": "risky", "category": "services", "name": "Risky", "revenue_type": "project",
     "speed_to_revenue": 9, "margin": 9, "startup_cost": 9, "automation": 9,
     "scalability": 8, "owner_effort": 2, "compliance_risk": 9},
]

def attestation(**overrides):
    result = {"verified_for_preparation": True,
              "attested_at": datetime.now(timezone.utc).isoformat(),
              "free_preparation_minutes": 90,
              "haeven_priority_protected": True,
              "paid_obligations_protected": True,
              "settlement_reserve_protected": True,
              "evidence_url": "https://example.org/capacity"}
    result.update(overrides)
    return result

class PortfolioTests(unittest.TestCase):
    def test_no_attestation_is_research_only(self):
        result = decide(MODELS)
        self.assertEqual(result["proposed"], [])
        self.assertFalse(result["external_execution_authorized"])
        self.assertEqual(result["eligible_count"], 2)

    def test_capacity_and_active_deduplicate(self):
        result = decide(MODELS, attestation(), active_ids=["one"])
        self.assertEqual([x["model_id"] for x in result["proposed"]], ["two"])
        self.assertEqual(result["active_ids_preserved"], ["one"])

    def test_stale_or_unprotected_capacity_denied(self):
        self.assertFalse(decide(MODELS, attestation(
            attested_at=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()))["proposed"])
        self.assertFalse(decide(MODELS, attestation(
            haeven_priority_protected=False))["proposed"])
        self.assertFalse(decide(MODELS, attestation(
            free_preparation_minutes=True))["proposed"])

    def test_review_persists_without_launching(self):
        with tempfile.TemporaryDirectory() as d:
            import sqlite3
            db = str(Path(d)/"review.sqlite")
            output = run(db)
            self.assertTrue(output["ranked_count"] > 0)
            self.assertEqual(output["proposed"], [])
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM apex_portfolio_reviews").fetchone()[0], 1)
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM apex_portfolio_active").fetchone()[0], 0)

if __name__ == "__main__":
    unittest.main()
