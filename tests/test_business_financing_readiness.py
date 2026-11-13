"""Tests for the offline financing readiness assistant."""
import unittest
from scripts.business_financing_readiness import assess

class FinancingReadinessTests(unittest.TestCase):
    def test_empty_profile_never_claims_ready(self):
        report = assess({})
        self.assertEqual(report["readiness"], "evidence_incomplete")
        self.assertIn("annual_revenue", report["missing_or_unsubstantiated"])

    def test_unsubstantiated_claims_remain_gaps(self):
        report = assess({"legal_business_name": "Example LLC",
                         "evidence": {"legal_business_name": {"status": "documented"}}})
        self.assertIn("legal_business_name", report["missing_or_unsubstantiated"])

    def test_sensitive_identifiers_rejected(self):
        with self.assertRaises(ValueError):
            assess({"ssn": "do-not-store"})
        with self.assertRaises(ValueError):
            assess({"routing_number": "do-not-store"})

    def test_owner_attested_not_misrepresented(self):
        report = assess({"legal_business_name": "Example LLC",
                         "evidence": {"legal_business_name": {"status": "owner_attested"}}})
        self.assertEqual(report["verified_or_attested_facts"]["legal_business_name"]["evidence_status"],
                         "owner_attested")

    def test_amount_validation(self):
        with self.assertRaises(ValueError):
            assess({"requested_amount": -500})
        with self.assertRaises(ValueError):
            assess({"requested_amount": True})

    def test_no_auto_submission(self):
        report = assess({})
        self.assertIn("specific informed owner approval",
                      " ".join(report["prohibited_actions"]))
        self.assertNotIn("approval_probability", report)

if __name__ == "__main__":
    unittest.main()
