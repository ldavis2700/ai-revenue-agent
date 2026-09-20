import unittest
from datetime import date
from decimal import Decimal

from scripts.consignment_payout import PayoutInput, PayoutStatus, calculate_payout


class CalculatePayoutTests(unittest.TestCase):
    def base(self, **overrides):
        values = {
            "sold_at": date(2026, 9, 1),
            "gross_sale": Decimal("1000.00"),
            "marketplace_fees": Decimal("100.00"),
            "approved_ad_fees": Decimal("25.00"),
            "other_deductions": Decimal("25.00"),
            "split_rate": Decimal("0.60"),
        }
        values.update(overrides)
        return PayoutInput(**values)

    def test_reconciles_deductions_and_split(self):
        result = calculate_payout(self.base(), as_of=date(2026, 10, 1))
        self.assertEqual(result.net_before_split, Decimal("850.00"))
        self.assertEqual(result.consignor_amount, Decimal("510.00"))
        self.assertEqual(result.status, PayoutStatus.ELIGIBLE)

    def test_return_window_boundary(self):
        data = self.base()
        self.assertEqual(
            calculate_payout(data, as_of=date(2026, 9, 30)).status,
            PayoutStatus.PENDING,
        )
        self.assertEqual(
            calculate_payout(data, as_of=date(2026, 10, 1)).status,
            PayoutStatus.ELIGIBLE,
        )

    def test_refund_reverses_even_after_window(self):
        result = calculate_payout(
            self.base(refund_amount=Decimal("1000")),
            as_of=date(2026, 10, 15),
        )
        self.assertEqual(result.status, PayoutStatus.REVERSED)
        self.assertEqual(result.consignor_amount, Decimal("0.00"))

    def test_hold_overrides_time_eligibility(self):
        result = calculate_payout(
            self.base(manual_hold=True), as_of=date(2026, 10, 15)
        )
        self.assertEqual(result.status, PayoutStatus.HELD)

    def test_deductions_cannot_make_negative_payout(self):
        result = calculate_payout(
            self.base(marketplace_fees=Decimal("1500")),
            as_of=date(2026, 10, 15),
        )
        self.assertEqual(result.net_before_split, Decimal("0.00"))
        self.assertEqual(result.consignor_amount, Decimal("0.00"))

    def test_rounds_currency_half_up(self):
        result = calculate_payout(
            self.base(
                gross_sale=Decimal("10.00"),
                marketplace_fees=0,
                approved_ad_fees=0,
                other_deductions=0,
                split_rate=Decimal("0.333"),
            ),
            as_of=date(2026, 10, 15),
        )
        self.assertEqual(result.consignor_amount, Decimal("3.33"))

    def test_rejects_invalid_inputs(self):
        for data in (
            self.base(gross_sale=Decimal("-1")),
            self.base(split_rate=Decimal("1.1")),
            self.base(return_window_days=-1),
        ):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    calculate_payout(data, as_of=date(2026, 10, 15))


if __name__ == "__main__":
    unittest.main()
