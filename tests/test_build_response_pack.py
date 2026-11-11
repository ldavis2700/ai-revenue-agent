import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_response_pack import build_files, write_pack, MESSAGES


class ResponsePackTests(unittest.TestCase):
    def setUp(self):
        self.profile = dict(company='Example Cleaning — fictional', services='residential cleaning',
            service_area='Example City', quote_process='a team member reviews the requested scope',
            escalation_contact='the business support team')

    def test_complete_pack_with_seven_categories_and_two_options(self):
        files = build_files(self.profile)
        page = files['response-pack.html'].decode()
        self.assertEqual(len(MESSAGES), 7)
        self.assertEqual(page.count('<strong>Option '), 14)
        self.assertIn('DRAFT', page)
        self.assertNotIn('{company}', page)
        rows = list(csv.reader(io.StringIO(files['inquiry-tracker.csv'].decode())))
        self.assertEqual(len(rows), 1)  # No invented customer rows.
        self.assertIn('opted_out', rows[0])
        self.assertIn('HOLD', files['response-use-guide.md'].decode())

    def test_profile_is_text_not_active_html_or_template_code(self):
        self.profile['company'] = '<script>alert(1)</script> {services} & Co'
        page = build_files(self.profile)['response-pack.html'].decode()
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('{services} &amp; Co', page)
        self.assertIn("default-src 'none'", page)

    def test_invalid_profiles_fail_before_creating_directory(self):
        for bad in (None, [], {}, {**self.profile, 'customer_email': 'private@example.test'},
                    {**self.profile, 'company': ''}, {**self.profile, 'services': []},
                    {**self.profile, 'services': 'x' * 301},
                    {**self.profile, 'company': 'Name\nInjected'}):
            with tempfile.TemporaryDirectory() as root:
                out = Path(root) / 'pack'
                with self.assertRaises(ValueError):
                    write_pack(bad, out)
                self.assertFalse(out.exists())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'pack'
            write_pack(self.profile, out)
            before = (out / 'response-pack.html').read_bytes()
            with self.assertRaises(FileExistsError):
                write_pack({**self.profile, 'company': 'Different'}, out)
            self.assertEqual((out / 'response-pack.html').read_bytes(), before)

    def test_hashes_match_files_without_claiming_delivery_or_payment(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'pack'
            manifest = write_pack(self.profile, out)
            self.assertEqual(json.loads((out / 'manifest.json').read_text()), manifest)
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(manifest['messages_sent'], 0)
            for key in ('delivery_verified', 'buyer_acceptance_verified', 'payment_verified'):
                self.assertFalse(manifest[key])
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)


if __name__ == '__main__':
    unittest.main()
