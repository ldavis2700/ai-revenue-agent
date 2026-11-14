"""Synthetic unit tests for hypothetical financing math; no applicant data."""
import unittest
from scripts.business_financing_readiness import assess


class RepaymentScenarioTests(unittest.TestCase):
    def _case(self, cash=None, debt=0):
        values = {"requested_amount": 12000,
                  "repayment_scenario": {"assumed_nominal_annual_rate_pct": 0,
                                         "assumed_term_months": 12},
                  "evidence": {
                      "requested_amount": {"status": "owner_attested"},
                      "existing_annual_debt_service": {"status": "owner_attested"}}}
        values["existing_annual_debt_service"] = debt
        if cash is not None:
            values["annual_cash_available_for_debt_service"] = cash
            values["evidence"]["annual_cash_available_for_debt_service"] = {
                "status": "owner_attested"}
        return values

    def test_no_rate_assumption_never_creates_quote(self):
        result = assess({})
        self.assertEqual(result["repayment_analysis"]["status"], "not_modeled")

    def test_zero_interest_and_positive_cash_downside(self):
        result = assess(self._case(cash=18000))
        analysis = result["repayment_analysis"]
        self.assertEqual(analysis["estimated_monthly_installment"], 1000)
        self.assertEqual(analysis["estimated_total_interest_excluding_fees"], 0)
        self.assertEqual(analysis["coverage"]["base_coverage_ratio"], 1.5)
        self.assertEqual(analysis["coverage"]["downside_coverage_ratio"], 1.2)
        self.assertEqual(analysis["status"], "illustrative_only")
        self.assertIn("fees", " ".join(analysis["missing_loan_costs"]))

    def test_no_fabricated_cash_flow_or_net_income_proxy(self):
        v = self._case()
        v["annual_net_income"] = 50000
        v["evidence"]["annual_net_income"] = {"status": "owner_attested"}
        self.assertEqual(assess(v)["repayment_analysis"]["coverage"]["status"],
                         "not_calculated")

    def test_negative_cash_flow_downside_is_more_conservative(self):
        result = assess(self._case(cash=-12000))
        cov = result["repayment_analysis"]["coverage"]
        self.assertLess(cov["downside_coverage_ratio"], cov["base_coverage_ratio"])

    def test_missing_principal_evidence_prevents_math(self):
        v = self._case(cash=18000)
        v["evidence"].pop("requested_amount")
        self.assertEqual(assess(v)["repayment_analysis"]["status"],
                         "insufficient_evidence")

    def test_invalid_and_nonfinite_assumptions_rejected(self):
        for term, rate in ((0, 10), (361, 10), (12, float("nan")),
                           (12, -1), (12, True), (12.5, 10)):
            v = self._case()
            v["repayment_scenario"] = {
                "assumed_term_months": term, "assumed_nominal_annual_rate_pct": rate}
            with self.subTest(term=term, rate=rate), self.assertRaises(ValueError):
                assess(v)

    def test_positive_interest_has_positive_interest_cost(self):
        v = self._case(cash=18000)
        v["repayment_scenario"]["assumed_nominal_annual_rate_pct"] = 12
        result = assess(v)["repayment_analysis"]
        self.assertGreater(result["estimated_monthly_installment"], 1000)
        self.assertGreater(result["estimated_total_interest_excluding_fees"], 0)


if __name__ == "__main__":
    unittest.main()
