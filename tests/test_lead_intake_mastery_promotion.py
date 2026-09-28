import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lead_intake_mastery_promotion.py"
SPEC = importlib.util.spec_from_file_location("lead_intake_mastery_promotion", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def delivery(index, buyer, *, contribution=10000, **overrides):
    item = {
        "delivery_id": f"delivery-{index}",
        "buyer_ref": f"redacted://buyer/{buyer}",
        "accepted_delivery": True,
        "settled_payment_verified": True,
        "collected_revenue_cents": 50000,
        "delivery_cost_cents": 45000 - contribution,
        "api_cost_cents": 5000,
        "human_hours": 2,
        "retained": False,
        "expanded": False,
        "confidentiality_cleared": True,
        "reusable_components": ["lead-router"],
    }
    item.update(overrides)
    return item


class LeadIntakeMasteryPromotionTests(unittest.TestCase):
    def test_empty_example_stays_learned_without_inventing_revenue(self):
        payload = json.loads((ROOT / "templates" / "home_services_lead_intake_mastery_promotion.example.json").read_text())
        result = module.evaluate(payload)
        self.assertEqual(result["mastery_candidate"], "learned")
        self.assertEqual(result["candidate_collected_revenue_cents"], 0)
        self.assertFalse(result["ledger_mutation_authorized"])

    def test_one_settled_accepted_delivery_validates_paid_engagement(self):
        result = module.evaluate({"deliveries": [delivery(1, "a")]})
        self.assertEqual(result["mastery_candidate"], "validated_paid_engagement")
        self.assertEqual(result["candidate_contribution_cents"], 10000)

    def test_two_independent_positive_deliveries_are_repeatable(self):
        result = module.evaluate({"deliveries": [delivery(1, "a"), delivery(2, "b")]})
        self.assertEqual(result["mastery_candidate"], "repeatable_positive_margin")

    def test_same_buyer_or_nonpositive_margin_cannot_be_repeatable(self):
        same = module.evaluate({"deliveries": [delivery(1, "a"), delivery(2, "a")]})
        self.assertEqual(same["mastery_candidate"], "validated_paid_engagement")
        loss = module.evaluate({"deliveries": [delivery(1, "a"), delivery(2, "b", contribution=0)]})
        self.assertEqual(loss["mastery_candidate"], "validated_paid_engagement")

    def test_retention_and_controls_are_required_for_scale(self):
        payload = {"support_risk_controlled": True, "acquisition_economics_verified": True,
                   "deliveries": [delivery(1, "a", retained=True), delivery(2, "b")]}
        self.assertEqual(module.evaluate(payload)["mastery_candidate"], "scale_candidate")

    def test_expansion_cross_buyer_reuse_and_clearance_enable_productize_candidate(self):
        payload = {"support_risk_controlled": True, "acquisition_economics_verified": True,
                   "deliveries": [delivery(1, "a", retained=True, expanded=True), delivery(2, "b")]}
        result = module.evaluate(payload)
        self.assertEqual(result["mastery_candidate"], "productize_candidate")
        self.assertEqual(result["reused_components_for_review"], ["lead-router"])

    def test_unsettled_revenue_fails_closed_and_is_not_counted(self):
        payload = {"deliveries": [delivery(1, "a", settled_payment_verified=False)]}
        result = module.evaluate(payload)
        self.assertFalse(result["promotion_review_ready"])
        self.assertEqual(result["candidate_collected_revenue_cents"], 0)
        self.assertIn("delivery_0_revenue_without_settled_payment", result["blockers"])

    def test_sensitive_data_fails_closed_without_echoing_value(self):
        result = module.evaluate({"buyer_email": "person@example.com", "deliveries": []})
        self.assertIn("raw_secret_or_contact_data_detected", result["blockers"])
        self.assertNotIn("person@example.com", json.dumps(result))

    def test_cli_exit_codes_distinguish_reviewable_blocked_and_malformed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps({"deliveries": []}))
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 0)
            path.write_text(json.dumps({"api_key": "private", "deliveries": []}))
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 1)
            path.write_text("not-json")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 2)


if __name__ == "__main__":
    unittest.main()
