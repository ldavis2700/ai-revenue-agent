import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("business_model_intelligence", ROOT / "scripts" / "business_model_intelligence.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class BusinessModelIntelligenceTests(unittest.TestCase):
    def test_catalog_is_valid_and_broad(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        self.assertGreaterEqual(len(catalog["models"]), 100)
        self.assertGreaterEqual(len({model["category"] for model in catalog["models"]}), 11)
        self.assertIn("partnerships", {model["category"] for model in catalog["models"]})

    def test_low_cost_fast_automatable_models_rank_well(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(
            catalog["models"],
            {"max_startup_cost": 3, "max_owner_effort": 5, "max_compliance_risk": 4,
             "min_speed_to_revenue": 7, "min_automation": 7},
        )
        eligible = [m for m in ranked if m["eligible"]]
        ids = {model["id"] for model in eligible[:25]}
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
        result = module.portfolio(module.rank_models(catalog["models"], {}), 5)
        self.assertTrue(result["guardrails"]["recommendation_only"])
        self.assertFalse(result["guardrails"]["automatic_spend"])
        self.assertTrue(all(m["execution_gate"] == "candidate_only" for m in result["candidates"]))

    def test_observed_success_materially_promotes_a_validated_model(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        constraints = {"max_startup_cost": 3, "max_owner_effort": 5, "max_compliance_risk": 4,
                       "min_speed_to_revenue": 5, "min_automation": 6}
        ranked = module.rank_models(catalog["models"], constraints)
        baseline_order = [m["id"] for m in ranked if m["eligible"]]
        baseline_position = baseline_order.index("directory")
        baseline_score = next(m["apex_score"] for m in ranked if m["id"] == "directory")

        plan = module.pursuit_plan(
            ranked,
            {"directory": {"observed_revenue": 1000, "observed_cost": 50,
                           "conversion_rate": 0.25, "evidence_quality": 1}},
            10,
        )
        pursue_order = [m["id"] for m in plan["pursue"]]
        directory = next(m for m in plan["pursue"] if m["id"] == "directory")

        self.assertEqual(plan["mode"], "continuous_opportunity_optimization")
        self.assertLess(pursue_order.index("directory"), baseline_position)
        self.assertGreater(directory["pursuit_score"], baseline_score)
        self.assertGreater(directory["observed_profit"], 0)
        self.assertIn("maximize durable risk-adjusted owner wealth", plan["objective"])

    def test_old_evidence_decays_influence(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        now = datetime(2026, 8, 31, tzinfo=timezone.utc)
        recent = module.pursuit_plan(
            ranked,
            {"directory": {"observed_revenue": 1000, "observed_cost": 50,
                           "conversion_rate": 0.25, "evidence_quality": 1,
                           "observed_at": "2026-08-31T00:00:00Z", "sample_size": 20}},
            40,
            now=now,
        )
        stale = module.pursuit_plan(
            ranked,
            {"directory": {"observed_revenue": 1000, "observed_cost": 50,
                           "conversion_rate": 0.25, "evidence_quality": 1,
                           "observed_at": "2026-05-03T00:00:00Z", "sample_size": 20}},
            40,
            now=now,
        )
        recent_directory = next(m for m in recent["pursue"] if m["id"] == "directory")
        stale_directory = next(m for m in stale["pursue"] if m["id"] == "directory")
        self.assertGreater(recent_directory["evidence_freshness"], stale_directory["evidence_freshness"])
        self.assertGreater(recent_directory["pursuit_score"], stale_directory["pursuit_score"])

    def test_invalid_or_future_observation_cannot_promote_a_model(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        for observed_at in (None, "", "not-a-date", 123, "2026-09-02T00:00:00Z"):
            with self.subTest(observed_at=observed_at):
                plan = module.pursuit_plan(ranked, {"directory": {
                    "observed_revenue": 1200, "observed_cost": 100,
                    "conversion_rate": 0.3, "evidence_quality": 1,
                    "sample_size": 20, "observed_at": observed_at,
                }}, 200, now=now)
                model = next(m for m in plan["pursue"] if m["id"] == "directory")
                self.assertEqual(model["evidence_freshness"], 0.0)
                self.assertEqual(model["pursuit_score"], model["apex_score"])
                self.assertEqual(model["experiment_state"], "validate")
                self.assertEqual(model["execution_gate"], "candidate_only")

    def test_legacy_missing_timestamp_and_valid_timezone_keep_compatibility(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        self.assertEqual(module.evidence_freshness({}, now=now), 1.0)
        self.assertEqual(module.evidence_freshness(
            {"observed_at": "2026-08-31T17:00:00-07:00"}, now=now), 1.0)
        self.assertEqual(module.evidence_freshness(
            {"observed_at": "2026-08-02T00:00:00Z"}, now=now), 0.5)

    def test_small_samples_are_tempered_and_winners_become_scale_candidates(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        now = datetime(2026, 8, 31, tzinfo=timezone.utc)
        plan = module.pursuit_plan(
            ranked,
            {
                "directory": {"observed_revenue": 1200, "observed_cost": 100,
                              "conversion_rate": 0.3, "evidence_quality": 1,
                              "observed_at": "2026-08-31T00:00:00Z", "sample_size": 20},
                "digital_templates": {"observed_revenue": 500, "observed_cost": 10,
                                      "conversion_rate": 0.5, "evidence_quality": 1,
                                      "observed_at": "2026-08-31T00:00:00Z", "sample_size": 2},
            },
            40,
            now=now,
        )
        directory = next(m for m in plan["pursue"] if m["id"] == "directory")
        templates = next(m for m in plan["pursue"] if m["id"] == "digital_templates")
        self.assertEqual(directory["experiment_state"], "scale_candidate")
        self.assertEqual(templates["experiment_state"], "validate")
        self.assertGreater(directory["evidence_reliability"], templates["evidence_reliability"])


if __name__ == "__main__":
    unittest.main()
