import os
import sqlite3
import tempfile
import unittest

from scripts import capture_inbound_lead


class InboundLeadTests(unittest.TestCase):
    def test_requires_affirmative_consent_and_privacy(self):
        lead, errors = capture_inbound_lead.normalize({
            'email': 'owner@example.com', 'company': 'Example Co'})
        self.assertIsNone(lead)
        self.assertIn('affirmative_contact_consent_required', errors)
        self.assertIn('privacy_acknowledgement_required', errors)

    def test_accepts_and_normalizes_owned_opt_in(self):
        lead, errors = capture_inbound_lead.normalize({
            'email': 'OWNER@EXAMPLE.COM', 'company': 'Example Co',
            'contact_consent': True, 'privacy_acknowledged': True})
        self.assertEqual(errors, [])
        self.assertTrue(lead['contact_allowed'])
        self.assertEqual(lead['contact_email'], 'owner@example.com')
        self.assertEqual(lead['source'], 'owned_inbound_opt_in')

    def test_honeypot_rejects_submission(self):
        lead, errors = capture_inbound_lead.normalize({
            'email': 'owner@example.com', 'company': 'Example Co',
            'contact_consent': True, 'privacy_acknowledged': True,
            'website_confirm': 'bot-filled'})
        self.assertIsNone(lead)
        self.assertIn('spam_check_failed', errors)

    def test_audit_hashes_email(self):
        lead, _ = capture_inbound_lead.normalize({
            'email': 'owner@example.com', 'company': 'Example Co',
            'contact_consent': True, 'privacy_acknowledged': True})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'agent.db')
            capture_inbound_lead.record_intake(lead, path)
            row = sqlite3.connect(path).execute(
                'SELECT email_hash, source FROM inbound_intake_audit').fetchone()
            self.assertNotEqual(row[0], 'owner@example.com')
            self.assertEqual(row[1], 'owned_inbound_opt_in')


if __name__ == '__main__':
    unittest.main()
