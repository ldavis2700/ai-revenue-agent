"""Synthetic-only regression tests; never use actual contractor/customer data."""
import unittest
from scripts.home_service_handoff_audit import analyze


def fixture():
    return {"schema_version": 1, "flows": [
        {"id": "inquiry_to_estimate", "cases": 20, "late_or_missing_handoffs": 4, "staff_review_minutes": 110},
        {"id": "job_to_invoice", "cases": 10, "late_or_missing_handoffs": 0, "staff_review_minutes": 85},
    ]}


class HandoffAuditTests(unittest.TestCase):
    def test_sorted_and_observed_not_roi(self):
        out = analyze(fixture())
        self.assertEqual([x["id"] for x in out["flows"]], ["inquiry_to_estimate", "job_to_invoice"])
        self.assertEqual(out["flows"][0]["late_or_missing_share_pct"], 20.0)
        self.assertEqual(out["flows"][0]["review_priority"], "investigate")
        self.assertNotIn("estimated_savings", str(out))

    def test_zero_baseline_is_not_zero_gap_rate(self):
        f = fixture()
        f["flows"][0].update(cases=0, late_or_missing_handoffs=0)
        out = analyze(f)
        row = next(x for x in out["flows"] if x["id"] == "inquiry_to_estimate")
        self.assertIsNone(row["late_or_missing_share_pct"])
        self.assertEqual(row["review_priority"], "measure_baseline")

    def test_reject_any_personal_or_unexpected_field(self):
        f = fixture()
        f["flows"][0]["customer_phone"] = "not allowed"
        with self.assertRaises(ValueError):
            analyze(f)

    def test_reject_bool_negative_and_excess_missing(self):
        for cases, misses in [(True, 0), (-1, 0), (1, 2), (1000001, 0)]:
            f = fixture()
            f["flows"][0].update(cases=cases, late_or_missing_handoffs=misses)
            with self.assertRaises(ValueError):
                analyze(f)

    def test_reject_duplicate_or_unapproved_flow(self):
        for second in ("inquiry_to_estimate", "customer_name"):
            f = fixture()
            f["flows"][1]["id"] = second
            with self.assertRaises(ValueError):
                analyze(f)

    def test_required_schema_is_exact(self):
        f = fixture()
        f["client"] = "none"
        with self.assertRaises(ValueError):
            analyze(f)


if __name__ == "__main__":
    unittest.main()
