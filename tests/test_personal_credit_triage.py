"""Smoke tests for personal credit triage (fictional data only)."""
import unittest
from scripts.personal_credit_triage import triage


class CreditTriageTests(unittest.TestCase):
    def test_flags_urgent_past_due_and_high_utilization(self):
        output = triage({"report_date": "2026-01-01",
            "accounts": [{"status": "Open", "balance": 95,
                          "credit_limit": 100, "past_due_amount": 15}]})
        reasons = {item["reason"] for item in output["findings"]}
        self.assertIn("reported_past_due", reasons)
        self.assertIn("high_individual_utilization", reasons)
        self.assertIn("payment", output["requires_owner_approval"])

    def test_no_personal_identifiers_in_output(self):
        result = triage({"accounts": [{"creditor_name": "FICTIONAL CREDIT",
            "account_number": "123456", "status": "Closed",
            "charge_off": True}], "collections": [{}]})
        text = str(result)
        self.assertNotIn("FICTIONAL CREDIT", text)
        self.assertNotIn("123456", text)
        self.assertIn("collection_verification", text)

    def test_missing_limit_is_not_utilization(self):
        output = triage({"accounts": [{"balance": 200, "credit_limit": None}]})
        self.assertFalse(output["findings"])


if __name__ == "__main__":
    unittest.main()
