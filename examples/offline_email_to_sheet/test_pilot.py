import csv
import json
import tempfile
import unittest
from pathlib import Path
from pilot import process

MESSAGES = [
    {"id":"demo-mail-0001","received_at":"2026-11-22T13:00:00Z","sender":"example-a@test.invalid","subject":"Request for an estimate"},
    {"id":"demo-mail-0002","received_at":"2026-11-22T13:10:00Z","sender":"example-b@test.invalid","subject":"Schedule a meeting"},
]


class OfflinePilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def rows(self):
        with (self.output / "synthetic_sheet.csv").open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_first_delivery(self):
        result = process(MESSAGES, self.output)
        self.assertEqual((result["new_records"], result["total_records"], result["external_calls"]), (2,2,0))
        self.assertEqual([row["category"] for row in self.rows()], ["lead", "appointment"])

    def test_idempotent_replay(self):
        process(MESSAGES, self.output)
        result = process(MESSAGES, self.output)
        self.assertEqual(result["new_records"], 0)
        self.assertEqual(len(self.rows()), 2)

    def test_duplicate_message_in_batch(self):
        result = process([MESSAGES[0], MESSAGES[0], MESSAGES[1]], self.output)
        self.assertEqual((result["new_records"], result["skipped_existing_or_repeat"]), (2,1))

    def test_failure_does_not_commit(self):
        process([MESSAGES[0]], self.output)
        original = (self.output / "synthetic_sheet.csv").read_bytes()
        result = process([MESSAGES[1]], self.output, inject_failure=True)
        self.assertEqual(result["state"], "failure")
        self.assertEqual(original, (self.output / "synthetic_sheet.csv").read_bytes())
        self.assertEqual(json.loads((self.output / "execution_log.json").read_text())["state"], "failure")

    def test_invalid_input_no_partial_commit(self):
        result = process([MESSAGES[0], {"id":"x","subject":"missing fields"}], self.output)
        self.assertEqual(result["state"], "failure")
        self.assertFalse((self.output / "synthetic_sheet.csv").exists())

    def test_spreadsheet_formula_payload_is_escaped(self):
        bad = [{"id":"demo-formula","received_at":"2026-11-22T00:00:00Z",
                "sender":"=HYPERLINK(\"bad\")","subject":"+2+2"}]
        result = process(bad, self.output)
        self.assertEqual(result["state"], "success")
        self.assertEqual(self.rows()[0]["sender"], "'=HYPERLINK(\"bad\")")
        self.assertEqual(self.rows()[0]["subject"], "'+2+2")

    def test_no_send_without_approval(self):
        process(MESSAGES, self.output)
        self.assertTrue(all(row["followup_status"] == "APPROVAL_REQUIRED_NO_EXTERNAL_ACTION" for row in self.rows()))


    def test_invalid_existing_sheet_fails_closed_and_logs(self):
        sheet = self.output / "synthetic_sheet.csv"
        sheet.write_text("unexpected_column\\nsynthetic\\n", encoding="utf-8")
        before = sheet.read_bytes()
        result = process(MESSAGES, self.output)
        self.assertEqual(result["state"], "failure")
        self.assertEqual(result["new_records"], 0)
        self.assertEqual(sheet.read_bytes(), before)
        self.assertEqual(json.loads((self.output / "execution_log.json").read_text(encoding="utf-8"))["state"], "failure")


if __name__ == "__main__":
    unittest.main()
