"""Regression checks for the self-contained, synthetic buyer-workflow demo."""
import sqlite3
import unittest

from evidence_review_demo import Evidence, propose, review_and_save, example


class EvidenceReviewDemoTests(unittest.TestCase):
    def setUp(self):
        self.evidence = Evidence("synthetic-001", "Invoice total USD 240.00", "local://synthetic-001")
        self.proposal = propose(self.evidence, "invoice_total", "240 USD", "total USD 240.00")
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def test_approval_persists_with_source(self):
        rowid = review_and_save(self.db, self.proposal, "approve")
        self.assertEqual(self.db.execute(
            "SELECT approved_value FROM approved_records WHERE id=?", (rowid,)
        ).fetchone()[0], "240 USD")
        self.assertEqual(self.db.execute(
            "SELECT source_reference FROM approved_records"
        ).fetchone()[0], "local://synthetic-001")

    def test_correction_records_original_and_updated(self):
        review_and_save(self.db, self.proposal, "correct", "245 USD")
        self.assertEqual(self.db.execute(
            "SELECT original_proposal, approved_value, review_decision FROM approved_records"
        ).fetchone(), ("240 USD", "245 USD", "corrected"))

    def test_rejection_has_no_write(self):
        self.assertIsNone(review_and_save(self.db, self.proposal, "reject"))
        self.assertEqual(self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall(), [])

    def test_false_quote_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact substring"):
            propose(self.evidence, "invoice_total", "999 USD", "total USD 999")

    def test_empty_evidence_rejected(self):
        with self.assertRaises(ValueError):
            propose(Evidence("synthetic", "", "local://x"), "field", "x", "x")

    def test_empty_correction_rejected(self):
        with self.assertRaises(ValueError):
            review_and_save(self.db, self.proposal, "correct", "")

    def test_approved_correction_mix_rejected(self):
        with self.assertRaises(ValueError):
            review_and_save(self.db, self.proposal, "approve", "245 USD")

    def test_sql_metacharacters_remain_data(self):
        review_and_save(self.db, self.proposal, "correct", "'); DROP TABLE approved_records;--")
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM approved_records"
        ).fetchone()[0], 1)

    def test_demo_human_review(self):
        self.assertTrue(example("approve")["record_saved"])
        self.assertFalse(example("reject")["record_saved"])
        self.assertEqual(example("correct", "250 USD")["record"]["approved_value"], "250 USD")


if __name__ == "__main__":
    unittest.main()
