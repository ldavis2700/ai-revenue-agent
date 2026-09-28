from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "sales" / "home-services-lead-intake-preview.html"


class HomeServicesLeadIntakeOfferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8")
        cls.lower = cls.html.lower()

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


if __name__ == "__main__":
    unittest.main()
