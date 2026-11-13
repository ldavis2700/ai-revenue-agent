"""Tests for Revenue Rescue's no-send opportunity preparation."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).parents[1] / "scripts" / "revenue_rescue_prepare.py"
spec = importlib.util.spec_from_file_location("revenue_rescue_prepare", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def lead(**kw):
    record = {"business_name": "Sample Repair Shop",
              "evidence_url": "https://example.org/contact",
              "observable_issue": "No online inquiry form visible on inspected page",
              "contact_permission": "inbound_request",
              "contact_email": "owner@example.org"}
    record.update(kw)
    return record


class RevenueRescueTests(unittest.TestCase):
    def test_authorized_input_prepares_only_draft(self):
        out = module.prepare([lead()])
        row = out["results"][0]
        self.assertEqual(row["status"], "draft_ready")
        self.assertFalse(row["sent"])
        self.assertFalse(row["paid"])
        self.assertEqual(row["collected_usd"], 0)
        self.assertEqual(out["sent_count"], 0)

    def test_no_permission_cannot_be_contacted(self):
        row = module.qualify(lead(contact_permission="publicly_listed"))
        self.assertEqual(row["status"], "review_only")
        self.assertNotIn("draft", row)

    def test_missing_observation_rejected(self):
        self.assertEqual(module.qualify(lead(observable_issue=""))["status"], "rejected")

    def test_insecure_or_invalid_evidence_url_rejected(self):
        self.assertEqual(module.qualify(lead(evidence_url="http://example.org"))["status"], "rejected")
        self.assertEqual(module.qualify(lead(evidence_url="https://localhost"))["status"], "rejected")

    def test_duplicate_drafts_blocked(self):
        out = module.prepare([lead(), lead()])
        self.assertEqual(out["draft_ready_count"], 1)
        self.assertEqual(out["results"][1]["reason"], "duplicate_contact")

    def test_no_inferred_revenue(self):
        out = module.prepare([lead(), lead(contact_email="next@example.org")])
        self.assertEqual(out["collected_usd"], 0)

    def test_capped_input(self):
        with self.assertRaises(ValueError):
            module.prepare([lead()] * 1001)


if __name__ == "__main__":
    unittest.main()
