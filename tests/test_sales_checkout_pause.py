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
        self.assertIn("payload.pain_point = String(payload.pain_point || '').trim()", self.html)
        self.assertIn("payload.pain_point.length < 12", self.html)

    def test_full_fictional_pack_is_accessible_without_pretending_a_sale(self):
        self.assertIn("docs/FICTIONAL_14_RESPONSE_PACK_DEMONSTRATION.md", self.html)
        self.assertIn("not a real client result", self.html)
        self.assertIn("not an automated sending service", self.html)

    def test_instant_examples_are_not_misrepresented_as_problem_specific(self):
        self.assertIn("General starter reply examples", self.html)
        self.assertIn("not responses tailored to the problem", self.html)
        self.assertIn("A custom preview requires human review", self.html)
        self.assertIn("These drafts are not yet tailored to that problem", self.html)
        self.assertIn("your specific problem awaits review", self.html)
        self.assertNotIn("Starter responses for ${company}, based on your request about", self.html)

    def test_canonical_sales_metadata_matches_public_railway_host(self):
        origin = "https://apex-content-worker-production.up.railway.app"
        legacy = "https://ai-revenue-agent-seven.vercel.app"
        pages = {
            "offer.html": "/",
            "home-services.html": "/home-services",
            "industries.html": "/industries",
            "partners.html": "/partners",
        }
        sitemap = (OFFER.parent / "sitemap.xml").read_text(encoding="utf-8")
        for filename, path in pages.items():
            with self.subTest(filename=filename):
                html = (OFFER.parent / filename).read_text(encoding="utf-8")
                url = origin + path
                self.assertIn(f'<link rel="canonical" href="{url}"', html)
                self.assertIn(f'<meta property="og:url" content="{url}"', html)
                self.assertIn(f"<loc>{url}</loc>", sitemap)
                self.assertNotIn(legacy, html)

    def test_both_home_services_ctas_preserve_bounded_campaign_tags(self):
        home = (OFFER.parent / "home-services.html").read_text(encoding="utf-8")
        self.assertIn('data-preview-campaign="home_services_hero"', home)
        self.assertIn('data-preview-campaign="home_services"', home)
        self.assertIn("new URLSearchParams(window.location.search)", home)
        self.assertIn("['utm_source', 'utm_medium', 'utm_campaign']", home)
        self.assertIn("replace(/[^a-zA-Z0-9._-]/g, '')", home)
        self.assertIn("slice(0, 80)", home)
        self.assertIn("document.querySelectorAll('a[data-preview-campaign]')", home)
        self.assertIn("link.href = '/?' + params.toString() + '#lead-form'", home)
        self.assertIn("params.set('utm_campaign', link.dataset.previewCampaign)", home)
        # Inbound utm_source or utm_medium alone must not erase per-link placement
        # attribution; an explicit inbound campaign must still be respected.
        self.assertIn("if (!params.has('utm_campaign'))", home)
        self.assertEqual(home.count("params.set('utm_campaign', link.dataset.previewCampaign)"), 1)
        self.assertIn('utm_campaign=home_services_hero#lead-form', home)
        self.assertIn('utm_campaign=home_services#lead-form', home)
        self.assertNotIn('checkout.stripe.com', home.lower())
        self.assertNotIn('buy.stripe.com', home.lower())

    def test_visible_copy_does_not_promise_live_checkout(self):
        self.assertIn("Online checkout is paused", self.html)
        self.assertIn("does not currently accept payments or subscriptions", self.html)
        self.assertIn('href="#lead-form"', self.html)


if __name__ == "__main__":
    unittest.main()
