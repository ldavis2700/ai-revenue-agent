"""Public offer must remain inquiry-only while payment rails are paused.

This is a static safety contract. It does not claim that a payment provider,
customer-response worker, or the deployed site has been activated.
"""
from pathlib import Path
import re
import unittest

OFFER = Path(__file__).resolve().parents[1] / "sales" / "offer.html"


class PausedCheckoutOfferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = OFFER.read_text(encoding="utf-8")

    def test_no_hardcoded_stripe_checkout_or_alternative_external_checkout(self):
        self.assertNotIn("buy.stripe.com", self.html.lower())
        self.assertNotIn("checkout.stripe.com", self.html.lower())
        hrefs = re.findall(r'<a\b[^>]*\bhref="([^"]+)"', self.html)
        self.assertTrue(hrefs, "expected to inspect actual offer CTAs")
        for href in hrefs:
            self.assertFalse(re.search(r'(?:checkout|payment|purchase)', href, re.I), href)

    def test_query_parameters_cannot_inject_a_checkout_destination(self):
        self.assertNotIn("params.get('setup')", self.html)
        self.assertNotIn("params.get('managed')", self.html)
        self.assertNotIn("enable('setup-link'", self.html)
        self.assertNotIn("enable('managed-link'", self.html)

    def test_consent_and_privacy_link_remain_on_free_inquiry(self):
        self.assertIn('id="lead-form"', self.html)
        self.assertIn('name="contact_consent"', self.html)
        self.assertIn('name="privacy_acknowledged"', self.html)
        self.assertIn('href="/privacy"', self.html)
        self.assertIn('data-lead-endpoint="https://wuzmqruxdclstezitsbf.supabase.co/functions/v1/revenue-inbound"', self.html)

    def test_tailored_preview_requires_privacy_safe_problem_description(self):
        self.assertIn('id="pain-help"', self.html)
        self.assertIn("Do not include customer names, addresses, door codes", self.html)
        self.assertRegex(self.html, r'<textarea[^>]+id="pain"[^>]+minlength="12"[^>]+maxlength="1000"[^>]+required>')
        self.assertIn('aria-describedby="pain-help"', self.html)

    def test_full_fictional_pack_is_accessible_without_pretending_a_sale(self):
        self.assertIn("docs/FICTIONAL_14_RESPONSE_PACK_DEMONSTRATION.md", self.html)
        self.assertIn("not a real client result", self.html)
        self.assertIn("not an automated sending service", self.html)

    def test_visible_copy_does_not_promise_live_checkout(self):
        self.assertIn("Online checkout is paused", self.html)
        self.assertIn("does not currently accept payments or subscriptions", self.html)
        self.assertIn('href="#lead-form"', self.html)


if __name__ == "__main__":
    unittest.main()
