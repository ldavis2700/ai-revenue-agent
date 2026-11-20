import unittest
from datetime import datetime, timezone

from scripts.app_venture_validation import assess

def valid():
    return {
        "candidate_id": "example-1",
        "lane": "owned_subscription_app",
        "buyer_problem": "Small businesses lose inbound inquiry follow-ups",
        "buyer_evidence_url": "https://example.org/research",
        "buyer_evidence_observed_at": datetime.now(timezone.utc).isoformat(),
        "permission_to_use_evidence": True,
        "original_solution": "An original, small business-specific reminder tool",
        "estimated_build_hours": 24,
        "estimated_monthly_cost_usd": 0,
        "customer_acquisition_channel": "opt-in pilot from existing audience",
        "customer_acquisition_permission": True,
        "technical_feasibility_review": True,
        "privacy_security_review": True,
        "platform_policy_review": True,
        "monetization_review": True,
        "distribution_test_defined": True,
        "retention_test_defined": True
    }

class AppVentureValidationTests(unittest.TestCase):
    def test_candidate_only_never_authorizes_external_action(self):
        result = assess(valid())
        self.assertEqual(result["state"], "pilot_preparation_candidate")
        self.assertFalse(result["external_actions_allowed"])
        self.assertFalse(result["monetization_activated"])
        self.assertIsNone(result["collected_revenue_usd"])
    def test_no_evidence_fails_closed(self):
        candidate = valid()
        candidate.pop("buyer_evidence_url")
        self.assertEqual(assess(candidate)["state"], "blocked")
    def test_missing_consent_blocks(self):
        candidate = valid()
        candidate["customer_acquisition_permission"] = False
        self.assertEqual(assess(candidate)["state"], "blocked")
    def test_paid_service_needs_real_buyer_scope(self):
        candidate = valid()
        candidate["lane"] = "bespoke_paid_app_service"
        self.assertIn("no_buyer_scope_evidence", assess(candidate)["reasons"])
    def test_no_charges_from_fake_profit(self):
        candidate = valid()
        candidate["estimated_monthly_cost_usd"] = -1
        self.assertEqual(assess(candidate)["state"], "blocked")
    def test_future_or_naive_date_blocks(self):
        candidate = valid()
        candidate["buyer_evidence_observed_at"] = "2099-01-01T00:00:00Z"
        self.assertEqual(assess(candidate)["state"], "blocked")

if __name__ == "__main__":
    unittest.main()
