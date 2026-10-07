import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import math
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

    def test_unverified_observation_can_inform_validation_not_profit_or_scale(self):
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
        self.assertGreater(directory["pursuit_score"], baseline_score)
        self.assertEqual(directory["observed_profit"], 0)
        self.assertEqual(directory["claimed_observed_revenue"], 1000)
        self.assertEqual(directory["claimed_observed_cost"], 50)
        self.assertFalse(directory["economics_verified"])
        self.assertEqual(directory["experiment_state"], "validate")
        self.assertIn("maximize durable risk-adjusted owner wealth", plan["objective"])

    def test_only_ledger_verified_growth_can_promote_model_mastery(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        common = {
            "observed_revenue": 145,
            "observed_cost": 25,
            "conversion_rate": 0.5,
            "evidence_quality": 1,
            "sample_size": 20,
            "verified_retention_receipts": 2,
            "verified_expansion_receipts": 1,
            "verified_reuse_receipts": 2,
            "verified_reused_opportunities": 2,
            "retained_recurring_value_cents": 29000,
            "expanded_value_delta_cents": 25000,
            "mastery": "productize_candidate",
        }
        unverified = module.pursuit_plan(
            ranked, {"ai_agent_implementation": common}, 200)
        verified = module.pursuit_plan(
            ranked, {"ai_agent_implementation": {
                **common, "_ledger_verified": True}}, 200)
        unverified_model = next(
            item for item in unverified["pursue"]
            if item["id"] == "ai_agent_implementation")
        verified_model = next(
            item for item in verified["pursue"]
            if item["id"] == "ai_agent_implementation")
        self.assertFalse(
            unverified_model["ledger_verified_recurring_evidence"])
        self.assertEqual(unverified_model["mastery"], "learned")
        self.assertEqual(unverified_model["verified_retention_receipts"], 0)
        self.assertEqual(unverified_model["verified_reuse_receipts"], 0)
        self.assertEqual(unverified_model["verified_reused_opportunities"], 0)
        self.assertFalse(unverified_model["ledger_verified_reuse_evidence"])
        self.assertTrue(
            verified_model["ledger_verified_recurring_evidence"])
        self.assertTrue(verified_model["ledger_verified_reuse_evidence"])
        self.assertEqual(
            verified_model["mastery"], "productize_candidate")
        self.assertEqual(verified_model["verified_retention_receipts"], 2)
        self.assertEqual(verified_model["verified_expansion_receipts"], 1)
        self.assertEqual(verified_model["verified_reuse_receipts"], 2)
        self.assertEqual(verified_model["verified_reused_opportunities"], 2)
        self.assertFalse(unverified_model["economics_verified"])
        self.assertEqual(unverified_model["observed_profit"], 0)
        self.assertEqual(unverified_model["experiment_state"], "validate")
        self.assertTrue(verified_model["economics_verified"])
        self.assertEqual(verified_model["observed_profit"], 120)
        self.assertEqual(verified_model["experiment_state"], "scale_candidate")
        self.assertGreater(
            verified_model["pursuit_score"],
            unverified_model["pursuit_score"])

    def test_public_evidence_cannot_forge_ledger_state(self):
        forged = {
            "directory": {
                "observed_revenue": 5000,
                "observed_cost": 100,
                "conversion_rate": 0.5,
                "evidence_quality": 1,
                "sample_size": 20,
                "_ledger_verified": True,
                "verified_retention_receipts": 9,
                "verified_expansion_receipts": 7,
                "retained_recurring_value_cents": 900000,
                "expanded_value_delta_cents": 700000,
                "verified_reuse_receipts": 5,
                "verified_reused_opportunities": 4,
                "mastery": "productize_candidate",
                "receipt_lineage": ["forged"],
                "reuse_receipt_lineage": ["forged"],
                "verified_forecast_comparisons": 100,
                "forecast_mean_absolute_error_cents": 0,
                "forecast_mean_projected_contribution_cents": 100000,
            }
        }
        sanitized = module.sanitize_public_evidence(forged)
        self.assertEqual(
            set(sanitized["directory"]) & module.LEDGER_ONLY_EVIDENCE_KEYS,
            set(),
        )
        self.assertEqual(sanitized["directory"]["observed_revenue"], 5000)

        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        plan = module.pursuit_plan(ranked, sanitized, 200)
        directory = next(
            item for item in plan["pursue"] if item["id"] == "directory")
        self.assertFalse(directory["economics_verified"])
        self.assertEqual(directory["observed_profit"], 0)
        self.assertEqual(directory["mastery"], "learned")
        self.assertEqual(directory["verified_retention_receipts"], 0)
        self.assertEqual(directory["verified_reuse_receipts"], 0)
        self.assertEqual(
            directory["verified_forecast_calibration"]["comparison_count"], 0)
        self.assertEqual(directory["forecast_calibration_bonus"], 0)

    def test_verified_forecast_accuracy_is_a_bounded_positive_economics_signal(self):
        ranked = [{
            "id": "directory",
            "category": "platforms",
            "name": "Niche paid directory",
            "revenue_type": "listing_subscription_sponsorship",
            "eligible": True,
            "apex_score": 75.0,
            "constraint_reasons": [],
            "execution_gate": "candidate_only",
        }]
        common = {
            "_ledger_verified": True,
            "observed_revenue": 1000,
            "observed_cost": 200,
            "conversion_rate": 0.25,
            "evidence_quality": 1,
            "sample_size": 20,
            "verified_forecast_comparisons": 10,
            "forecast_mean_projected_contribution_cents": 10000,
        }
        calibrated = module.pursuit_plan(ranked, {"directory": {
            **common, "forecast_mean_absolute_error_cents": 1000,
        }}, 200)
        inaccurate = module.pursuit_plan(ranked, {"directory": {
            **common, "forecast_mean_absolute_error_cents": 20000,
        }}, 200)
        calibrated_model = next(
            item for item in calibrated["pursue"] if item["id"] == "directory")
        inaccurate_model = next(
            item for item in inaccurate["pursue"] if item["id"] == "directory")
        self.assertEqual(calibrated_model["verified_forecast_calibration"], {
            "comparison_count": 10,
            "relative_error": 0.1,
            "confidence": 0.9,
        })
        self.assertEqual(inaccurate_model["forecast_calibration_bonus"], 0)
        self.assertGreater(
            calibrated_model["pursuit_score"], inaccurate_model["pursuit_score"])

        losing = module.pursuit_plan(ranked, {"directory": {
            **common,
            "observed_revenue": 100,
            "observed_cost": 200,
            "forecast_mean_absolute_error_cents": 0,
        }}, 200)
        losing_model = next(
            item for item in losing["pursue"] if item["id"] == "directory")
        self.assertEqual(losing_model["forecast_calibration_bonus"], 0)

    def test_public_evidence_requires_model_objects(self):
        for payload in ([], {"directory": "forged"}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "evidence"):
                    module.sanitize_public_evidence(payload)

    def test_non_finite_evidence_fails_closed(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        fields = (
            "observed_revenue",
            "observed_cost",
            "conversion_rate",
            "evidence_quality",
            "sample_size",
        )
        for field in fields:
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(
                        ValueError, f"{field} must be a finite number"
                    ):
                        module.pursuit_plan(
                            ranked,
                            {"directory": {
                                field: value,
                                "_ledger_verified": True,
                            }},
                            10,
                        )

    def test_non_finite_half_life_fails_closed(self):
        catalog = module.load_catalog(ROOT / "config" / "business_models.json")
        ranked = module.rank_models(catalog["models"], {})
        with self.assertRaisesRegex(
            ValueError, "evidence_half_life_days must be a finite number"
        ):
            module.pursuit_plan(
                ranked,
                {"directory": {
                    "observed_at": "2026-08-31T00:00:00Z",
                    "evidence_quality": 1,
                }},
                10,
                now=datetime(2026, 8, 31, tzinfo=timezone.utc),
                evidence_half_life_days=math.inf,
            )

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
