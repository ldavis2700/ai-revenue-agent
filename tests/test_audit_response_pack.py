import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_response_pack import PackAuditError, audit_pack
from scripts.build_response_pack import write_pack


class AuditResponsePackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pack = Path(self.tmp.name) / 'pack'
        write_pack({
            'company': 'Fictional Cleaning Co.',
            'services': 'routine cleaning',
            'service_area': 'Example County',
            'quote_process': 'manager confirms scope before quoting',
            'escalation_contact': 'the on-duty manager',
        }, self.pack)

    def _resign(self, name):
        manifest_path = self.pack / 'manifest.json'
        data = json.loads(manifest_path.read_text())
        data['files'][name] = hashlib.sha256((self.pack / name).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(data))

    def test_real_builder_integrity_pass_is_not_buyer_acceptance(self):
        report = audit_pack(self.pack)
        self.assertTrue(report['integrity_verified'])
        self.assertEqual(report['draft_reply_count'], 14)
        for key in ('substantive_buyer_fact_review_verified', 'buyer_acceptance_verified',
                    'delivery_authorized', 'payment_or_settlement_verified'):
            self.assertFalse(report[key])

    def test_changed_response_bytes_fail(self):
        with (self.pack / 'response-pack.html').open('ab') as handle:
            handle.write(b'tamper')
        with self.assertRaisesRegex(PackAuditError, 'digest mismatch'):
            audit_pack(self.pack)

    def test_manually_resigned_incomplete_response_fails(self):
        page = self.pack / 'response-pack.html'
        page.write_text(page.read_text().replace('<strong>Option 1.', '<strong>Variant 1.', 1))
        self._resign('response-pack.html')
        with self.assertRaisesRegex(PackAuditError, 'incomplete'):
            audit_pack(self.pack)

    def test_resigned_tracker_customer_row_rejected(self):
        with (self.pack / 'inquiry-tracker.csv').open('a') as handle:
            handle.write('private-customer,inquiry,open,true,false,call,,,,\n')
        self._resign('inquiry-tracker.csv')
        with self.assertRaisesRegex(PackAuditError, 'no customer rows'):
            audit_pack(self.pack)

    def test_extra_file_and_symlink_are_rejected(self):
        (self.pack / 'extra.txt').write_text('oops')
        with self.assertRaisesRegex(PackAuditError, 'file set'):
            audit_pack(self.pack)
        (self.pack / 'extra.txt').unlink()
        (self.pack / 'inquiry-tracker.csv').unlink()
        (self.pack / 'inquiry-tracker.csv').symlink_to(self.pack / 'response-pack.html')
        with self.assertRaisesRegex(PackAuditError, 'unsafe'):
            audit_pack(self.pack)

    def test_false_claims_in_manifest_rejected(self):
        file = self.pack / 'manifest.json'
        obj = json.loads(file.read_text())
        obj['delivery_verified'] = True
        file.write_text(json.dumps(obj))
        with self.assertRaisesRegex(PackAuditError, 'unsent'):
            audit_pack(self.pack)

    def test_world_accessible_directory_rejected(self):
        self.pack.chmod(0o755)
        with self.assertRaisesRegex(PackAuditError, 'group/other'):
            audit_pack(self.pack)

    def test_directory_symlink_rejected(self):
        link = Path(self.tmp.name) / 'alias'
        link.symlink_to(self.pack, target_is_directory=True)
        with self.assertRaisesRegex(PackAuditError, 'symlink'):
            audit_pack(link)


if __name__ == '__main__':
    unittest.main()
