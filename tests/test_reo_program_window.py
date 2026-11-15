"""Protected REO sale-window regression tests; never authorize bids."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "reo_source_screen", Path(__file__).resolve().parents[1] / "scripts/reo_source_screen.py"
)
reo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reo)

AS_OF = "2026-11-15"
URL = "https://homepath.fanniemae.com/property-finder"
HUD_URL = "https://www.hudhomestore.gov/"
BASE = {
    "address": "Fictional Example Home",
    "official_listing_url": URL,
    "source_verified": True,
    "checked_on": AS_OF,
    "status": "active",
    "asking_price": 100000,
    "investor_purchase_permitted": True,
    "investor_eligibility_source_url": URL,
    "investor_eligibility_checked_on": AS_OF,
    "official_asset_id": "FICT-123",
    "investor_phase_asset_id": "FICT-123",
    "first_listed_on": "2026-07-01",
    "first_listed_verified": True,
    "first_listed_source_url": URL,
    "continuous_listing_verified": True,
    "continuous_listing_source_url": URL,
    "continuous_listing_checked_on": AS_OF,
}


def screened(item):
    return reo.screen({"as_of": AS_OF, "listings": [item]})["listings"][0]


class InvestorPhaseTests(unittest.TestCase):
    def test_homepath_generic_investor_permission_is_not_property_phase_proof(self):
        result = screened({**BASE, "reo_program": "fannie_homepath"})
        self.assertIn("investor_program_window_unverified", result["blocking_reasons"])
        self.assertEqual(result["screen_status"], "needs_evidence")
        self.assertTrue(result["research_trigger_met"])
        self.assertIsNone(result["underwriting"]["scenario_max_offer"])
        self.assertFalse(result["external_action_allowed"])

    def test_homepath_unexpired_first_look_is_not_qualified(self):
        item = {**BASE, "reo_program": "fannie_homepath",
                "investor_phase": "first_look_expired",
                "investor_phase_verified": True,
                "investor_eligible_from": "2026-11-16",
                "investor_phase_source_url": URL,
                "investor_phase_checked_on": AS_OF}
        self.assertIn("investor_program_window_unverified", screened(item)["blocking_reasons"])

    def test_homepath_listing_phase_evidence_can_clear_research_gate_only(self):
        item = {**BASE, "reo_program": "fannie_homepath",
                "investor_phase": "first_look_expired",
                "investor_phase_verified": True,
                "investor_eligible_from": "2026-11-10",
                "investor_phase_source_url": URL,
                "investor_phase_checked_on": AS_OF}
        result = screened(item)
        self.assertEqual(result["screen_status"], "research_only_candidate")
        self.assertFalse(result["underwriting"]["ready"])
        self.assertFalse(result["external_action_allowed"])

    def test_hud_exclusive_phase_cannot_be_treated_as_extended(self):
        item = {**BASE, "reo_program": "hud_home_store",
                "investor_phase": "exclusive_listing",
                "investor_phase_verified": True,
                "investor_eligible_from": "2026-11-01",
                "investor_phase_source_url": HUD_URL,
                "investor_phase_checked_on": AS_OF}
        self.assertIn("investor_program_window_unverified", screened(item)["blocking_reasons"])

    def test_hud_extended_requires_fresh_property_specific_proof(self):
        item = {**BASE, "reo_program": "hud_home_store",
                "investor_phase": "extended_listing",
                "investor_phase_verified": True,
                "investor_eligible_from": "2026-11-10",
                "investor_phase_source_url": HUD_URL,
                "investor_phase_checked_on": "2026-10-01"}
        self.assertIn("investor_program_window_unverified", screened(item)["blocking_reasons"])
        item["investor_phase_checked_on"] = AS_OF
        result = screened(item)
        self.assertEqual(result["screen_status"], "research_only_candidate")
        self.assertFalse(result["external_action_allowed"])

    def test_cross_property_phase_evidence_is_rejected(self):
        item = {**BASE, "reo_program": "fannie_homepath",
                "investor_phase": "first_look_expired",
                "investor_phase_verified": True,
                "investor_eligible_from": "2026-11-10",
                "investor_phase_source_url": URL,
                "investor_phase_checked_on": AS_OF,
                "investor_phase_asset_id": "DIFFERENT-ASSET"}
        self.assertIn("investor_program_window_unverified", screened(item)["blocking_reasons"])

    def test_unknown_or_other_portal_does_not_infer_a_program_phase(self):
        result = screened(BASE)
        self.assertEqual(result["screen_status"], "research_only_candidate")
        self.assertFalse(result["external_action_allowed"])


if __name__ == "__main__":
    unittest.main()
