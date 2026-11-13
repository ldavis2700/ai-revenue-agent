"""Fail-closed REO screening regression tests."""
import unittest
from scripts.reo_screening import screen_reo


def candidate():
    return {
        "address": "Example property, sample city",
        "source_url": "https://example.org/listing/1",
        "as_of": "2026-11-13",
        "listing_price": "120000",
        "days_on_market": 105,
        "price_cuts": 1,
        "arv_low": "200000",
        "arv_high": "240000",
        "repairs_low": "20000",
        "repairs_high": "40000",
        "holding_closing_costs": "10000",
        "desired_fee": "5000",
    }


class ReoScreeningTests(unittest.TestCase):
    def test_conservative_max_offer(self):
        result = screen_reo(candidate())
        self.assertEqual(result["max_offer_heuristic_usd"], "85000.00")
        self.assertTrue(result["watchlist_filter"])
        self.assertFalse(result["automatic_offer_authorized"])
        self.assertFalse(result["automatic_outreach_authorized"])

    def test_two_price_cuts_qualifies(self):
        value = candidate()
        value.update(days_on_market=30, price_cuts=2)
        self.assertTrue(screen_reo(value)["watchlist_filter"])

    def test_exactly_ninety_days_does_not_qualify(self):
        value = candidate()
        value.update(days_on_market=90, price_cuts=1)
        self.assertFalse(screen_reo(value)["watchlist_filter"])

    def test_missing_source_fails_closed(self):
        value = candidate()
        del value["source_url"]
        with self.assertRaises(ValueError):
            screen_reo(value)

    def test_negative_and_nonfinite_numbers_rejected(self):
        for invalid in ("-1", "NaN", "Infinity"):
            value = candidate()
            value["repairs_high"] = invalid
            with self.assertRaises(ValueError):
                screen_reo(value)

    def test_negative_offer_clamped(self):
        value = candidate()
        value["repairs_high"] = "180000"
        self.assertEqual(screen_reo(value)["max_offer_heuristic_usd"], "0.00")

    def test_inverted_ranges_rejected(self):
        value = candidate()
        value["arv_low"] = "250000"
        with self.assertRaises(ValueError):
            screen_reo(value)


if __name__ == "__main__":
    unittest.main()
