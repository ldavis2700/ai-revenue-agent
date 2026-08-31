import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "business_model_intelligence", ROOT / "scripts" / "business_model_intelligence.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class BusinessModelIntelligenceTests(unittest.TestCase):
    def test_catalog_is_valid_and_broad(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        self.assertGreaterEqual(len(catalog["models"]), 35)
        categories = {model["category"] for model in catalog["models"]}
        self.assertGreaterEqual(len(categories), 8)

    def test_low_cost_fast_automatable_models_rank_well(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(
            catalog["models"],
            {
                "max_startup_cost": 3,
                "max_owner_effort": 5,
                "max_compliance_risk": 4,
                "min_speed_to_revenue": 7,
                "min_automation": 7,
            },
        )
        eligible = [model for model in ranked if model["eligible"]]
        ids = {model["id"] for model in eligible[:10]}
        self.assertIn("ai_automation_agency", ids)
        self.assertIn("productized_service", ids)

    def test_constraints_block_expensive_or_high_effort_candidates(self):
        model = {
            "id": "x", "category": "test", "name": "X", "revenue_type": "test",
            "speed_to_revenue": 10, "margin": 10, "startup_cost": 9,
            "automation": 10, "scalability": 10, "owner_effort": 9,
            "compliance_risk": 1,
        }
        ok, reasons = module.eligible(model, {"max_startup_cost": 3, "max_owner_effort": 5})
        self.assertFalse(ok)
        self.assertIn("startup_cost_above_limit", reasons)
        self.assertIn("owner_effort_above_limit", reasons)

    def test_portfolio_never_authorizes_execution(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        result = module.portfolio(ranked, 5)
        self.assertTrue(result["guardrails"]["recommendation_only"])
        self.assertFalse(result["guardrails"]["automatic_spend"])
        self.assertTrue(all(m["execution_gate"] == "candidate_only" for m in result["candidates"]))


if __name__ == "__main__":
    unittest.main()
