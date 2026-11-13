"""Fail closed when the public buyer-preview form drifts from API intake source.

Static source contract only: it neither contacts production nor claims deployment.
Releases must independently verify the LIVE frontend, function and consent path.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
OFFER = ROOT / 'sales' / 'offer.html'
INTAKE = ROOT / 'supabase' / 'functions' / 'revenue-inbound' / 'lead-intake.mjs'
HANDLER = ROOT / 'supabase' / 'functions' / 'revenue-inbound' / 'index.ts'
WORKER = ROOT / 'content_worker.py'
PUBLIC_ORIGIN = 'https://apex-content-worker-production.up.railway.app'
API_ORIGIN = 'https://wuzmqruxdclstezitsbf.supabase.co'


class ReleaseIntakeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = OFFER.read_text(encoding='utf-8')
        cls.intake = INTAKE.read_text(encoding='utf-8')
        cls.handler = HANDLER.read_text(encoding='utf-8')
        cls.worker = WORKER.read_text(encoding='utf-8')

    def test_form_names_remain_compatible_with_server_input(self):
        names = set(re.findall(r'\bname="([a-z_]+)"', self.html))
        for name in ('company_name', 'contact_email', 'pain_point',
                     'contact_consent', 'privacy_acknowledged', 'website_confirm'):
            with self.subTest(name=name):
                self.assertIn(name, names)
                self.assertIn('payload.' + name, self.intake)
        self.assertIn('new FormData(form)', self.html)
        self.assertIn('normalizeLeadPayload(payload)', self.handler)

    def test_problem_bounds_agree_on_client_and_server(self):
        m = re.search(r'<textarea\b(?=[^>]*\bname="pain_point")([^>]*)>', self.html)
        self.assertIsNotNone(m, 'buyer problem textarea missing')
        attrs = m.group(1)
        lower = re.search(r'\bminlength="(\d+)"', attrs)
        upper = re.search(r'\bmaxlength="(\d+)"', attrs)
        self.assertIsNotNone(lower)
        self.assertIsNotNone(upper)
        lo, hi = int(lower.group(1)), int(upper.group(1))
        self.assertEqual((lo, hi), (12, 1000))
        self.assertIn(f'payload.pain_point.length < {lo}', self.html)
        self.assertIn(f'payload.pain_point.length > {hi}', self.html)
        self.assertIn(f'problem.length < {lo} || problem.length > {hi}', self.intake)
        self.assertIn('typeof payload.pain_point === "string"', self.intake)
        self.assertIn('payload.pain_point = String(payload.pain_point || \'\').trim()', self.html)

    def test_explicit_consent_and_rejection_precede_database_insert(self):
        for key in ('contact_consent', 'privacy_acknowledged'):
            self.assertIn(f'payload.{key} = form.elements.{key}.checked', self.html)
            self.assertIn(f'payload.{key} !== true', self.intake)
        self.assertIn('errors: normalized.errors }, 422', self.handler)
        self.assertLess(self.handler.index('normalizeLeadPayload(payload)'),
                        self.handler.index('insertUniqueLead(supabase.from("inbound_leads")'))
        self.assertIn('ignoreDuplicates: true', self.intake)

    def test_offer_api_host_and_checkout_pause_stay_consistent(self):
        self.assertIn(f'data-lead-endpoint="{API_ORIGIN}/functions/v1/revenue-inbound"', self.html)
        self.assertIn(f'origin === "{PUBLIC_ORIGIN}"', self.intake)
        self.assertIn(f'connect-src {API_ORIGIN}', self.worker)
        self.assertIn('Online checkout is paused', self.html)
        self.assertNotIn('buy.stripe.com', self.html.lower())
        self.assertNotIn('checkout.stripe.com', self.html.lower())
        self.assertIn("form.addEventListener('submit'", self.html)
        self.assertIn("if (!response.ok) throw new Error('request_failed')", self.html)


if __name__ == '__main__':
    unittest.main()
