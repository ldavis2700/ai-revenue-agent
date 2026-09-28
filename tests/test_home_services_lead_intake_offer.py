from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "sales" / "home-services-lead-intake-preview.html"
DIAGNOSTIC = ROOT / "templates" / "home_services_lead_intake_diagnostic.md"
PILOT_SCOPE = ROOT / "templates" / "home_services_lead_intake_pilot_scope.md"
MANAGED_RUNBOOK = ROOT / "templates" / "home_services_lead_intake_managed_service_runbook.md"
ACQUISITION = ROOT / "templates" / "home_services_lead_intake_acquisition_playbook.md"


class HomeServicesLeadIntakeOfferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8")
        cls.lower = cls.html.lower()
        cls.diagnostic = DIAGNOSTIC.read_text(encoding="utf-8").lower()
        cls.pilot_scope = PILOT_SCOPE.read_text(encoding="utf-8").lower()
        cls.managed_runbook = MANAGED_RUNBOOK.read_text(encoding="utf-8").lower()
        cls.acquisition = ACQUISITION.read_text(encoding="utf-8").lower()

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

    def test_managed_runbook_requires_evidence_before_recurring_operation(self):
        for text in (
            "reusable operating template only",
            "accepted paid pilot",
            "recurring scope accepted through an authorized channel",
            "contract and payment/funding states independently classified",
            "unknown or expired gate pauses service",
            "anything outside this inventory requires change control",
        ):
            self.assertIn(text, self.managed_runbook)

    def test_managed_runbook_operationalizes_controls_and_incidents(self):
        for text in (
            "## operating cadence",
            "## monitoring and alerts",
            "## exception and fail-closed matrix",
            "## consent, privacy, and security review",
            "## qa sampling and release control",
            "## incident response and rollback",
            "never weaken a privacy, security, consent, or audit control",
        ):
            self.assertIn(text, self.managed_runbook)

    def test_managed_runbook_separates_economics_revenue_and_productization(self):
        for text in (
            "## unit-economics ledger",
            "only verified settled funds enter collected revenue",
            "invoiced/approved, collected, withdrawable, and actually received",
            "outcome or usage pricing remains excluded",
            "## renewal, expansion, and upsell",
            "## termination and offboarding",
            "no promotion gate is earned from this template alone",
        ):
            self.assertIn(text, self.managed_runbook)

    def test_acquisition_playbook_prioritizes_real_buyer_intent(self):
        for text in (
            "active buyer replies, interviews, invitations, offers, and contracts",
            "current marketplace posts with verified application eligibility",
            "existing consented inbound requests",
            "never use bought, rented, scraped, harvested, or guessed contact lists",
            "never convert an invitation sent to other freelancers",
        ):
            self.assertIn(text, self.acquisition)

    def test_acquisition_playbook_preserves_contact_spend_and_contract_gates(self):
        for text in (
            "never spend connects, bid credits",
            "without the required channel-specific approval",
            "never accept or sign materially consequential custom terms",
            "direct outreach is prohibited until",
            "stop immediately on opt-out",
            "do not send the skeleton unchanged",
        ):
            self.assertIn(text, self.acquisition)

    def test_acquisition_playbook_separates_funnel_and_verified_revenue(self):
        for text in (
            "prospect → qualified opportunity → proposal → buyer reply/interview",
            "funded/billable work",
            "only independently verified settled funds count as collected revenue",
            "never report proposal value as revenue",
            "repeatability requires at least two independent profitable accepted deliveries",
            "no acquisition or mastery claim is earned from this playbook alone",
        ):
            self.assertIn(text, self.acquisition)


if __name__ == "__main__":
    unittest.main()
