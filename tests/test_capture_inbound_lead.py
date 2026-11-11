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


    def test_replayed_id_cannot_overwrite_original_consent_audit(self):
        first, errors = capture_inbound_lead.normalize({
            'id': 'replayed-id', 'email': 'original@example.test',
            'company': 'Original Co', 'contact_consent': True,
            'privacy_acknowledged': True, 'consent_version': 'contact-v1'})
        self.assertEqual(errors, [])
        later = dict(first)
        later['contact_email'] = 'changed@example.test'
        later['source'] = 'untrusted_replay'
        later['metadata'] = {**first['metadata'],
                             'consent_version': 'replaced-v9',
                             'consent_recorded_at': '2099-01-01T00:00:00+00:00'}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'agent.db')
            capture_inbound_lead.record_intake(first, path)
            with sqlite3.connect(path) as db:
                original = db.execute(
                    'SELECT email_hash, source, consent_version, consent_recorded_at, received_at '
                    'FROM inbound_intake_audit WHERE lead_id = ?', ('replayed-id',)).fetchone()
            capture_inbound_lead.record_intake(later, path)
            with sqlite3.connect(path) as db:
                saved = db.execute(
                    'SELECT email_hash, source, consent_version, consent_recorded_at, received_at '
                    'FROM inbound_intake_audit WHERE lead_id = ?', ('replayed-id',)).fetchone()
                count = db.execute('SELECT COUNT(*) FROM inbound_intake_audit').fetchone()[0]
            self.assertEqual(saved, original)
            self.assertEqual(count, 1)

    def test_distinct_ids_still_record_independent_audits(self):
        lead, errors = capture_inbound_lead.normalize({
            'id': 'first-id', 'email': 'first@example.test',
            'company': 'Example Co', 'contact_consent': True,
            'privacy_acknowledged': True})
        self.assertEqual(errors, [])
        second = dict(lead)
        second['id'] = 'second-id'
        second['contact_email'] = 'second@example.test'
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'agent.db')
            capture_inbound_lead.record_intake(lead, path)
            capture_inbound_lead.record_intake(second, path)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute(
                    'SELECT COUNT(*) FROM inbound_intake_audit').fetchone()[0], 2)

if __name__ == '__main__':
    unittest.main()
