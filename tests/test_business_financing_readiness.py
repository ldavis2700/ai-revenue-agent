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


    def test_sensitive_identifier_nested_in_source_documents_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Sensitive financing profile"):
            assess({"source_documents": [{"notes": {"routing-number": "never-log"}}]})

    def test_sensitive_identifier_nested_in_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Sensitive financing profile"):
            assess({"evidence": {"industry": {"status": "documented",
                                             "source": {"BANK ACCOUNT": "never-log"}}}})

    def test_safe_document_references_remain_usable(self):
        result = assess({"source_documents": [{"kind": "registration", "ref": "private:sample"}],
                         "evidence": {"source_documents": {"status": "owner_attested"}}})
        self.assertIn("source_documents", result["verified_or_attested_facts"])

    def test_owner_attested_not_misrepresented(self):
        report = assess({"legal_business_name": "Example LLC",
                         "evidence": {"legal_business_name": {"status": "owner_attested"}}})
        self.assertEqual(report["verified_or_attested_facts"]["legal_business_name"]["evidence_status"],
                         "owner_attested")

    def test_evidence_reference_cannot_be_nontext_or_multiline(self):
        for bad in ([{"ref": "private:fixture"}], {"ref": "private:fixture"}, 12,
                    True, "line\nsecond", "x" * 513):
            with self.subTest(type=type(bad).__name__), self.assertRaises(ValueError):
                assess({"annual_revenue": 100,
                        "evidence": {"annual_revenue": {"status": "documented",
                                                        "source": bad}}})

    def test_blank_documented_reference_remains_unsubstantiated(self):
        report = assess({"annual_revenue": 100,
                         "evidence": {"annual_revenue": {"status": "documented",
                                                         "source": "   "}}})
        self.assertIn("annual_revenue", report["missing_or_unsubstantiated"])
        self.assertNotIn("annual_revenue", report["verified_or_attested_facts"])

    def test_amount_validation(self):
        with self.assertRaises(ValueError):
            assess({"requested_amount": -500})
        with self.assertRaises(ValueError):
            assess({"requested_amount": True})

    def test_documented_zero_income_and_debt_remain_facts(self):
        profile = {
            "annual_revenue": 0,
            "annual_net_income": -100,
            "existing_annual_debt_service": 0,
            "evidence": {
                key: {"status": "documented", "source": "PRIVATE_FIXTURE"}
                for key in ("annual_revenue", "annual_net_income", "existing_annual_debt_service")
            },
        }
        report = assess(profile)
        for key in ("annual_revenue", "annual_net_income", "existing_annual_debt_service"):
            self.assertIn(key, report["verified_or_attested_facts"])
            self.assertNotIn(key, report["missing_or_unsubstantiated"])
        self.assertEqual(report["readiness"], "evidence_incomplete")

    def test_nonfinite_or_negative_cashflow_rejected(self):
        for profile in (
            {"annual_revenue": -1},
            {"existing_annual_debt_service": -1},
            {"requested_amount": float("nan")},
            {"annual_revenue": float("inf")},
        ):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                assess(profile)


    def test_cash_flow_is_validated_without_optional_repayment_scenario(self):
        for bad in ("not a number", float("nan"), float("inf"), 10**1000, True):
            with self.subTest(type=type(bad).__name__), self.assertRaises(ValueError):
                assess({"annual_cash_available_for_debt_service": bad,
                        "evidence": {"annual_cash_available_for_debt_service":
                                     {"status": "documented", "source": "fictional:test"}}})

    def test_oversized_integers_fail_closed_instead_of_crashing_cycle(self):
        for name in ("requested_amount", "annual_revenue", "annual_net_income",
                     "existing_annual_debt_service"):
            with self.subTest(field=name), self.assertRaises(ValueError):
                assess({name: 10**1000})

    def test_non_scalar_evidence_status_is_rejected(self):
        for value in ([], {}, ["documented"]):
            with self.subTest(type=type(value).__name__), self.assertRaises(ValueError):
                assess({"industry": "software", "evidence": {"industry": {"status": value}}})

    def test_valid_negative_cashflow_remains_a_documented_fact(self):
        report = assess({"annual_cash_available_for_debt_service": -1200,
                         "evidence": {"annual_cash_available_for_debt_service":
                                      {"status": "documented", "source": "fictional:test"}}})
        self.assertEqual(report["verified_or_attested_facts"][
            "annual_cash_available_for_debt_service"]["value"], -1200)

    def test_no_auto_submission(self):
        report = assess({})
        self.assertIn("specific informed owner approval",
                      " ".join(report["prohibited_actions"]))
        self.assertNotIn("approval_probability", report)

if __name__ == "__main__":
    unittest.main()
