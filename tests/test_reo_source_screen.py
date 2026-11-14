"""Regression tests for the offline, research-only REO listing gate."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "reo_source_screen", Path(__file__).resolve().parents[1] / "scripts/reo_source_screen.py"
)
reo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reo)

URL = "https://www.homesteps.com/listingdetails/example"
BASE = {"as_of": "2026-11-13", "listings": [{
    "address": "Test", "official_listing_url": URL, "source_verified": True,
    "checked_on": "2026-11-13", "status": "active", "asking_price": 100000,
    "investor_purchase_permitted": True,
    "investor_eligibility_source_url": URL,
    "investor_eligibility_checked_on": "2026-11-13",
}]}

# Fictional but internally complete listing-level evidence to exercise the
# underwriting validator independently of the new outer listing gates.
QUALIFIED = {**BASE["listings"][0],
             "first_listed_on": "2026-08-01",
             "first_listed_verified": True, "first_listed_source_url": URL,
             "continuous_listing_verified": True,
             "continuous_listing_source_url": URL,
             "continuous_listing_checked_on": "2026-11-13"}


class ScreenTests(unittest.TestCase):
    def test_missing_dom_and_cuts_fails_closed(self):
        r = reo.screen(BASE)["listings"][0]
        self.assertEqual(r["screen_status"], "needs_evidence")
        self.assertIsNone(r["underwriting"]["scenario_max_offer"])

    def test_90_day_trigger_is_research_only(self):
        d = {**BASE, "listings": [{**BASE["listings"][0], "first_listed_on": "2026-08-01", "first_listed_verified": True, "first_listed_source_url": URL,
            "continuous_listing_verified": True, "continuous_listing_source_url": URL,
            "continuous_listing_checked_on": "2026-11-13"}]}
        r = reo.screen(d)["listings"][0]
        self.assertTrue(r["research_trigger_met"])
        self.assertFalse(r["external_action_allowed"])

    def test_elapsed_days_do_not_claim_continuous_dom(self):
        d = {**BASE, "listings": [{**BASE["listings"][0],
            "first_listed_on": "2026-07-01", "first_listed_verified": True,
            "first_listed_source_url": URL}]}
        r = reo.screen(d)["listings"][0]
        self.assertEqual(r["calendar_days_since_first_listing"], 135)
        self.assertIsNone(r["days_on_market_verified"])
        self.assertFalse(r["research_trigger_met"])

    def test_same_day_multiple_price_changes_are_not_distinct_cuts(self):
        h = [{"dated_on": "2026-11-10", "source_url": URL,
              "price": p, "verified": True} for p in (130000, 115000, 100000)]
        r = reo.screen({**BASE, "listings": [{**BASE["listings"][0], "price_history": h}]})["listings"][0]
        self.assertEqual(r["verified_price_cuts"], 0)
        self.assertIn("price_history_not_verified", r["blocking_reasons"])
        self.assertFalse(r["research_trigger_met"])

    def test_two_real_price_cuts(self):
        h = [{"dated_on": d, "source_url": URL, "price": p, "verified": True} for d, p in [
            ("2026-09-01", 130000), ("2026-10-01", 115000), ("2026-11-10", 100000)]]
        r = reo.screen({**BASE, "listings": [{**BASE["listings"][0], "price_history": h}]})["listings"][0]
        self.assertEqual(r["verified_price_cuts"], 2)
        self.assertTrue(r["research_trigger_met"])

    def test_uncertain_or_future_history_not_two_cuts(self):
        h = [{"dated_on": d, "source_url": URL, "price": p} for d, p in [
            ("2026-12-01", 130000), ("2026-10-01", 115000), ("2026-11-10", 100000)]]
        r = reo.screen({**BASE, "listings": [{**BASE["listings"][0], "price_history": h}]})["listings"][0]
        self.assertEqual(r["verified_price_cuts"], 0)

    def test_investor_prohibition_always_excludes(self):
        r = reo.screen({**BASE, "listings": [{
            **BASE["listings"][0], "investor_purchase_permitted": False,
            "first_listed_on": "2026-01-01", "first_listed_verified": True, "first_listed_source_url": URL}]})["listings"][0]
        self.assertEqual(r["screen_status"], "excluded")

    def test_sourced_arv_cost_scenario_is_not_offer(self):
        x = {"closed_comps": [{"property_address": f"Fictional Sold Home {i}", "source_url": URL + str(i), "closed_on": "2026-06-01", "sold_price": 200000} for i in range(3)],
            "arv": 200000, "arv_source_url": URL,
            "repairs_low": 10000, "repairs_high": 25000, "repair_quote_source_url": URL,
            "repair_quote_checked_on": "2026-11-12", "acquisition_cost": 5000,
            "selling_cost": 10000, "holding_cost": 5000, "uncertainty_reserve": 5000}
        eligible = {**BASE["listings"][0], "underwriting": x,
                    "first_listed_on": "2026-08-01",
                    "first_listed_verified": True, "first_listed_source_url": URL,
                    "continuous_listing_verified": True,
                    "continuous_listing_source_url": URL,
                    "continuous_listing_checked_on": "2026-11-13"}
        r = reo.screen({**BASE, "listings": [eligible]})["listings"][0]
        self.assertTrue(r["underwriting"]["ready"])
        self.assertEqual(r["underwriting"]["scenario_max_offer"], "90000.00")
        self.assertFalse(r["external_action_allowed"])

    def test_duplicate_closed_comps_fail(self):
        x = {"closed_comps": [{"property_address": "Fictional Duplicate Home", "source_url": URL, "closed_on": "2026-06-01", "sold_price": 200000} for _ in range(3)],
            "arv": 200000, "arv_source_url": URL,
            "repairs_low": 10000, "repairs_high": 25000, "repair_quote_source_url": URL,
            "repair_quote_checked_on": "2026-11-12", "acquisition_cost": 5000,
            "selling_cost": 10000, "holding_cost": 5000, "uncertainty_reserve": 5000}
        result = reo.screen({**BASE, "listings": [{**QUALIFIED, "underwriting": x}]})
        self.assertFalse(result["listings"][0]["underwriting"]["ready"])
        self.assertIn("duplicate_closed_comp_source", result["listings"][0]["underwriting"]["reasons"])

    def test_distinct_urls_same_property_fail_closed(self):
        comps = [
            {"property_address": " 123 Fictional Street ", "source_url": URL + str(i),
             "closed_on": "2026-06-01", "sold_price": 200000}
            for i in range(3)
        ]
        comps[1]["property_address"] = "123  FICTIONAL street"
        comps[2]["property_address"] = "Other Fictional Street"
        x = {"closed_comps": comps, "arv": 200000, "arv_source_url": URL,
             "repairs_low": 10000, "repairs_high": 25000,
             "repair_quote_source_url": URL, "repair_quote_checked_on": "2026-11-12",
             "acquisition_cost": 5000, "selling_cost": 10000,
             "holding_cost": 5000, "uncertainty_reserve": 5000}
        r = reo.screen({**BASE, "listings": [{**QUALIFIED, "underwriting": x}]})["listings"][0]
        self.assertFalse(r["underwriting"]["ready"])
        self.assertIn("duplicate_closed_comp_property", r["underwriting"]["reasons"])
        self.assertIsNone(r["underwriting"]["scenario_max_offer"])

    def test_malformed_unhashable_comp_source_fails_closed_not_exception(self):
        comps = [
            {"property_address": f"Fictional Sold Home {i}", "source_url": URL + str(i),
             "closed_on": "2026-06-01", "sold_price": 200000}
            for i in range(3)
        ]
        comps[1]["source_url"] = ["not", "a", "url"]
        x = {"closed_comps": comps, "arv": 200000, "arv_source_url": URL,
             "repairs_low": 10000, "repairs_high": 25000,
             "repair_quote_source_url": URL, "repair_quote_checked_on": "2026-11-12",
             "acquisition_cost": 5000, "selling_cost": 10000,
             "holding_cost": 5000, "uncertainty_reserve": 5000}
        r = reo.screen({**BASE, "listings": [{**QUALIFIED, "underwriting": x}]})["listings"][0]
        self.assertFalse(r["underwriting"]["ready"])
        self.assertIn("invalid_closed_comp_evidence", r["underwriting"]["reasons"])

    def test_extreme_finite_arv_fails_closed_not_exception(self):
        x = {"closed_comps": [
                {"property_address": f"Fictional Sold Home {i}",
                 "source_url": URL + str(i), "closed_on": "2026-06-01",
                 "sold_price": 200000} for i in range(3)],
             "arv": "1e200", "arv_source_url": URL,
             "repairs_low": 10000, "repairs_high": 25000,
             "repair_quote_source_url": URL, "repair_quote_checked_on": "2026-11-12",
             "acquisition_cost": 5000, "selling_cost": 10000,
             "holding_cost": 5000, "uncertainty_reserve": 5000}
        r = reo.screen({**BASE, "listings": [{**QUALIFIED, "underwriting": x}]})["listings"][0]
        self.assertFalse(r["underwriting"]["ready"])
        self.assertIn("scenario_arithmetic_out_of_range", r["underwriting"]["reasons"])
        self.assertIsNone(r["underwriting"]["scenario_max_offer"])

    def test_false_and_negative_financials_fail(self):
        x = {"arv": False, "arv_source_url": URL, "repairs_low": -1}
        r = reo.screen({**BASE, "listings": [{**BASE["listings"][0], "underwriting": x}]})["listings"][0]
        self.assertFalse(r["underwriting"]["ready"])

    def test_duplicate_is_rejected(self):
        r = reo.screen({**BASE, "listings": BASE["listings"] + BASE["listings"]})["listings"][1]
        self.assertIn("duplicate_listing", r["blocking_reasons"])

    def test_unverified_listing_date_has_no_dom(self):
        result = reo.screen({**BASE, "listings": [{
            **BASE["listings"][0], "first_listed_on": "2026-01-01"}]})
        self.assertIsNone(result["listings"][0]["days_on_market_verified"])

    def test_stale_listing_snapshot_does_not_pass_current_source(self):
        item = {**BASE["listings"][0], "checked_on": "2026-11-01"}
        r = reo.screen({**BASE, "listings": [item]})["listings"][0]
        self.assertIn("official_source_stale", r["blocking_reasons"])
        self.assertFalse(r["underwriting"]["ready"])

    def test_stale_investor_first_look_evidence_is_blocked(self):
        item = {**BASE["listings"][0], "investor_eligibility_checked_on": "2026-10-01"}
        r = reo.screen({**BASE, "listings": [item]})["listings"][0]
        self.assertIn("investor_eligibility_evidence_missing_or_stale", r["blocking_reasons"])

    def test_stale_continuous_dom_does_not_qualify(self):
        item = {**BASE["listings"][0], "first_listed_on": "2026-06-01",
                "first_listed_verified": True, "first_listed_source_url": URL,
                "continuous_listing_verified": True,
                "continuous_listing_source_url": URL,
                "continuous_listing_checked_on": "2026-10-01"}
        r = reo.screen({**BASE, "listings": [item]})["listings"][0]
        self.assertIsNone(r["days_on_market_verified"])
        self.assertFalse(r["research_trigger_met"])

    def test_duplicate_property_under_different_official_urls(self):
        first = BASE["listings"][0]
        duplicate = {**first, "official_listing_url": URL + "/alternate",
                     "address": "  TEST  "}
        second = reo.screen({**BASE, "listings": [first, duplicate]})["listings"][1]
        self.assertIn("duplicate_listing", second["blocking_reasons"])

    def test_sourced_math_not_released_for_unqualified_listing(self):
        x = {"closed_comps": [{"property_address": f"Fictional Sold {i}",
              "source_url": URL + str(i), "closed_on": "2026-09-01",
              "sold_price": 200000} for i in range(3)],
             "arv": 200000, "arv_source_url": URL,
             "repairs_low": 10000, "repairs_high": 20000,
             "repair_quote_source_url": URL, "repair_quote_checked_on": "2026-11-13",
             "acquisition_cost": 3000, "selling_cost": 9000,
             "holding_cost": 3000, "uncertainty_reserve": 5000}
        r = reo.screen({**BASE, "listings": [{**BASE["listings"][0], "underwriting": x}]})["listings"][0]
        self.assertFalse(r["underwriting"]["ready"])
        self.assertIsNone(r["underwriting"]["scenario_max_offer"])

    def test_missing_authoritative_check(self):
        r = reo.screen({**BASE, "listings": [{
            **BASE["listings"][0], "source_verified": False}]})["listings"][0]
        self.assertIn("official_source_not_verified", r["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
