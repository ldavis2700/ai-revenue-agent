import unittest
from scripts.business_financing_packet import render

class BusinessFinancingPacketTests(unittest.TestCase):
    def test_missing_facts_are_not_invented(self):
        packet=render({})
        self.assertIn("MISSING / UNVERIFIED",packet)
        self.assertNotIn("100% approved",packet)
        self.assertIn("No application",packet)

    def test_attestation_is_labeled(self):
        p=render({"legal_business_name":"Sample LLC",
                  "evidence":{"legal_business_name":{"status":"owner_attested"}}})
        self.assertIn("Sample LLC [owner_attested]",p)
        self.assertIn("Annual revenue: **MISSING / UNVERIFIED**",p)

    def test_documented_value_has_reference(self):
        p=render({"industry":"software",
                  "evidence":{"industry":{"status":"documented","source":"private:registration"}}})
        self.assertIn("software [documented; private reference: private:registration]",p)

    def test_no_estimate_without_actual_lender_terms_and_cashflow(self):
        packet = render({"requested_amount": 12000,
                         "evidence": {"requested_amount": {"status": "owner_attested"}}})
        self.assertIn("CANNOT ASSESS", packet)
        self.assertNotIn("scheduled monthly payment:", packet)

    def test_documented_synthetic_stress_case(self):
        figures = {
            "requested_amount": 12000,
            "annual_interest_rate_pct": 12,
            "term_months": 12,
            "upfront_fees": 300,
            "annual_cash_available_for_debt_service": 25000,
            "existing_annual_debt_service": 0,
        }
        profile = {**figures, "evidence": {
            k: {"status": "documented", "source": "test-only:fictional"}
            for k in figures
        }}
        packet = render(profile)
        self.assertIn("scheduled monthly payment:", packet)
        self.assertIn("conservative cash-flow downside", packet)
        self.assertIn("not a lender quote or approval", packet)
        self.assertIn("existing annual debt service: $0.00", packet)

    def test_nonnumeric_terms_not_accepted(self):
        figures = {
            "requested_amount": 12000,
            "annual_interest_rate_pct": float("nan"),
            "term_months": 12,
            "upfront_fees": 0,
            "annual_cash_available_for_debt_service": 5000,
            "existing_annual_debt_service": 0,
        }
        profile = {**figures, "evidence": {
            k: {"status": "documented", "source": "test-only:fictional"}
            for k in figures
        }}
        with self.assertRaises(ValueError):
            render(profile)

    def test_sensitive_top_level_identifier_rejected(self):
        with self.assertRaises(ValueError):
            render({"bank_account":"123"})

if __name__ == "__main__":
    unittest.main()
