from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "sales" / "home-services-lead-intake-preview.html"
DIAGNOSTIC = ROOT / "templates" / "home_services_lead_intake_diagnostic.md"
PILOT_SCOPE = ROOT / "templates" / "home_services_lead_intake_pilot_scope.md"


class HomeServicesLeadIntakeOfferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8")
        cls.lower = cls.html.lower()
        cls.diagnostic = DIAGNOSTIC.read_text(encoding="utf-8").lower()
        cls.pilot_scope = PILOT_SCOPE.read_text(encoding="utf-8").lower()

    def test_preview_cannot_be_mistaken_for_a_live_purchase_page(self):
        self.assertIn('name="robots" content="noindex,nofollow"', self.lower)
        self.assertIn("preview only — not currently available for purchase", self.lower)
        self.assertNotIn("buy.stripe.com", self.lower)
        self.assertNotIn("<form", self.lower)

    def test_offer_ladder_and_test_bands_are_explicit(self):
        for text in ("paid diagnostic", "bounded pilot", "managed automation",
                     "$250–$500", "$1,500–$3,000", "$500–$1,500"):
            self.assertIn(text.lower(), self.lower)

    def test_consent_safety_and_acceptance_gates_are_explicit(self):
        for text in ("consented", "opt-out", "suppression", "human escalation",
                     "no duplicate outbound action", "rollback", "manual override"):
            self.assertIn(text, self.lower)

    def test_outcome_pricing_requires_verified_attribution(self):
        self.assertIn("outcome-pricing gate", self.lower)
        self.assertIn("not offered until a paid pilot establishes reliable attribution", self.lower)
        self.assertIn("never represented as collected client revenue", self.lower)

    def test_page_disclaims_results_and_validation(self):
        self.assertIn("no booking, revenue, savings, or roi is guaranteed", self.lower)
        self.assertIn("not a case study or proof of demand", self.lower)
        self.assertIn("no customer result, paid validation, or revenue claim", self.lower)

    def test_diagnostic_covers_delivery_and_acceptance_controls(self):
        for heading in (
            "## evidence boundary",
            "## baseline metrics",
            "## consent, privacy, and operational controls",
            "## deterministic versus ai decision",
            "## bounded pilot scope",
            "## qa and acceptance matrix",
            "## measurement and attribution",
            "## unit economics",
            "## buyer acceptance",
            "## promotion gates",
        ):
            self.assertIn(heading, self.diagnostic)

    def test_diagnostic_preserves_evidence_and_revenue_boundaries(self):
        for text in (
            "redacted evidence references",
            "not a case study",
            "no guarantee",
            "outcome pricing is prohibited",
            "collected revenue: $0",
            "settled payment plus accepted",
        ):
            self.assertIn(text, self.diagnostic)

    def test_diagnostic_exercises_high_risk_failure_modes(self):
        for scenario in (
            "duplicate lead/action",
            "opted-out or suppressed record",
            "quiet hours / timezone boundary",
            "emergency or unsafe language",
            "unavailable integration",
            "retry / idempotency",
            "conflicting crm state",
            "prompt injection / malicious text",
            "audit trail / rollback",
        ):
            self.assertIn(scenario, self.diagnostic)

    def test_pilot_scope_is_bounded_and_does_not_grant_authority(self):
        for text in (
            "draft scope template — not an offer, contract, invoice",
            "one consented inbound lead source",
            "one qualification and routing path",
            "one authorized crm / booking destination",
            "anything not enumerated above is out of scope",
            "work may begin only after",
        ):
            self.assertIn(text, self.pilot_scope)

    def test_pilot_scope_preserves_safety_payment_and_revenue_gates(self):
        for text in (
            "outcome pricing is excluded",
            "collected revenue $0 unless independently verified as settled",
            "do not record proposal value as collected revenue",
            "explicit owner review before acceptance",
            "a failed safety control stops the pilot",
            "settled payment plus accepted delivery",
        ):
            self.assertIn(text, self.pilot_scope)

    def test_pilot_scope_requires_launch_and_rollback_evidence(self):
        for text in (
            "## launch gates",
            "integration access expressly authorized",
            "consent, opt-out, suppression, quiet hours",
            "duplicate, retry, idempotency, timeout, stale-state, and rollback",
            "prompt-injection paths fail closed",
            "volume, duration, api-spend, and action caps",
            "## stop, incident, and rollback rules",
        ):
            self.assertIn(text, self.pilot_scope)


if __name__ == "__main__":
    unittest.main()
