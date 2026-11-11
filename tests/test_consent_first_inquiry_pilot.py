"""Regression tests for an offline, no-send customer inquiry demonstration."""
import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'consent_first_inquiry_pilot.py'
spec = importlib.util.spec_from_file_location('consent_first_inquiry_pilot', SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
FIELDS = list(pilot.REQUIRED)


def row(ident, *, consent='true', opted_out='false', status='new', email='a@example.test'):
    return dict(inquiry_id=ident, email=email, message='Help please',
                consent_to_reply=consent, opted_out=opted_out, status=status)


class PilotTests(unittest.TestCase):
    def run_rows(self, values):
        with tempfile.TemporaryDirectory() as folder:
            source, dest = Path(folder) / 'in.csv', Path(folder) / 'out.csv'
            with source.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader(); writer.writerows(values)
            summary = pilot.process(source, dest)
            with dest.open(newline='', encoding='utf-8') as handle:
                output = list(csv.DictReader(handle))
            self.assertTrue(all(item['sent'] == 'false' for item in output))
            self.assertEqual(summary['messages_sent'], 0)
            with self.assertRaises(FileExistsError):
                pilot.process(source, dest)
            return summary, output

    def test_late_opt_out_blocks_first_duplicate_too(self):
        summary, output = self.run_rows([row('DUP'), row('dup', opted_out='true')])
        self.assertEqual(summary['eligible_for_human_review'], 0)
        self.assertEqual([item['decision'] for item in output], ['duplicate_or_invalid_id'] * 2)
        self.assertFalse(any(item['draft_reply'] for item in output))

    def test_conflicting_duplicate_email_blocks_both(self):
        summary, _ = self.run_rows([row('id-1'), row('id-1', email='b@example.test')])
        self.assertEqual(summary['eligible_for_human_review'], 0)

    def test_valid_unique_is_review_only(self):
        summary, output = self.run_rows([row('good_001'), row('no-consent', consent='yes'),
                                        row('optout', opted_out='true'), row('closed', status='closed')])
        self.assertEqual(summary['eligible_for_human_review'], 1)
        self.assertTrue(output[0]['draft_reply'])
        self.assertTrue(all(not item['draft_reply'] for item in output[1:]))

    def test_csv_formula_identifier_not_exported(self):
        summary, output = self.run_rows([row('=HYPERLINK("https://evil.example")')])
        self.assertEqual(summary['eligible_for_human_review'], 0)
        self.assertEqual(output[0]['inquiry_id'], '')
        self.assertEqual(output[0]['decision'], 'duplicate_or_invalid_id')

    def test_duplicate_header_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, dest = Path(folder) / 'in.csv', Path(folder) / 'out.csv'
            source.write_text('inquiry_id,inquiry_id,email,message,consent_to_reply,opted_out,status\na,a,a@example.test,hi,true,false,new\n')
            with self.assertRaises(ValueError):
                pilot.process(source, dest)
            self.assertFalse(dest.exists())

    def test_missing_columns_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, dest = Path(folder) / 'in.csv', Path(folder) / 'out.csv'
            source.write_text('id,email\na,a@example.test\n')
            with self.assertRaises(ValueError):
                pilot.process(source, dest)
            self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()

