"""Offline tests for the read-only legacy checkout retirement guard."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_live_offer.py"
SPEC = importlib.util.spec_from_file_location("verify_live_offer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class VerifyLiveOfferTests(unittest.TestCase):
    def setUp(self):
        self.valid_page = ("<html><p>Online checkout is paused; this page does not currently "
                           "accept payments or subscriptions.</p>"
                           '<form><input name="contact_consent"/><input name="privacy_acknowledged"/></form>'
                           "</html>")

    def fetch(self, url):
        if url.startswith(MODULE.LEGACY):
            path = url.removeprefix(MODULE.LEGACY)
            return MODULE.Result(307, MODULE.expected_target(path))
        if url.startswith(MODULE.CURRENT):
            return MODULE.Result(200, body=self.valid_page)
        raise AssertionError("unexpected test URL")

    def test_read_only_positive_legacy_and_current_acceptance(self):
        result = MODULE.audit(self.fetch)
        self.assertEqual(result["legacy_redirects_checked"], 4)
        self.assertEqual(result["railway_offer_pages_checked"], 2)
        self.assertFalse(result["collection_ready"])
        self.assertFalse(result["revenue_verified"])

    def test_detects_old_live_html_even_when_source_is_paused(self):
        def stale(url):
            if url == MODULE.LEGACY + "/":
                return MODULE.Result(200, body='<a href="https://buy.stripe.com/foo">Buy</a>')
            return self.fetch(url)
        with self.assertRaisesRegex(MODULE.AuditFailure, "legacy_not_307"):
            MODULE.audit(stale)

    def test_rejects_unexpected_redirect_or_missing_path(self):
        source = MODULE.LEGACY + "/offer.html"
        for location in ("https://unrelated.example/offer.html", MODULE.CURRENT + "/"):
            with self.subTest(location=location):
                with self.assertRaisesRegex(MODULE.AuditFailure, "unexpected_redirect_destination"):
                    MODULE.verify_redirect(MODULE.Result(307, location), source, "/offer.html")

    def test_legacy_query_must_be_preserved(self):
        path = MODULE.LEGACY_PATHS[-1]
        with self.assertRaisesRegex(MODULE.AuditFailure, "unexpected_redirect_destination"):
            MODULE.verify_redirect(MODULE.Result(307, MODULE.CURRENT + "/offer.html"), MODULE.LEGACY + path, path)

    def test_rejects_wrong_status_and_missing_location(self):
        with self.assertRaisesRegex(MODULE.AuditFailure, "legacy_not_307"):
            MODULE.verify_redirect(MODULE.Result(301, MODULE.CURRENT + "/"), MODULE.LEGACY + "/", "/")
        with self.assertRaisesRegex(MODULE.AuditFailure, "missing_location"):
            MODULE.verify_redirect(MODULE.Result(307), MODULE.LEGACY + "/", "/")

    def test_railway_page_must_not_offer_stripe_or_query_checkout(self):
        for bad in ("<a href='https://buy.stripe.com/x'>Buy</a>", "checkout.stripe.com", "params.get('setup')", "params.get('managed')"):
            with self.subTest(bad=bad):
                with self.assertRaises(MODULE.AuditFailure):
                    MODULE.verify_offer(MODULE.Result(200, body=self.valid_page + bad), "/")

    def test_railway_page_requires_paused_copy_and_consent(self):
        for body in ("<html></html>", self.valid_page.replace('name="contact_consent"', ""), self.valid_page.replace("Online checkout is paused", "Checkout open")):
            with self.subTest(body=body[:40]):
                with self.assertRaises(MODULE.AuditFailure):
                    MODULE.verify_offer(MODULE.Result(200, body=body), "/")

    def test_no_false_success_for_failed_network_response(self):
        def offline(_url):
            raise OSError("dns unavailable")
        with self.assertRaises(OSError):
            MODULE.audit(offline)


if __name__ == "__main__":
    unittest.main()
