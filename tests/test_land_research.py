import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "land_research", ROOT / "scripts" / "land_research.py")
land = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(land)
NOW = datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)


def approved_policy():
    checks = {name: {"reviewed": True, "source_urls": [f"https://law.example/{name}"]}
              for name in land.REQUIRED_LEGAL_CHECKS}
    return {"default_status": "QUARANTINED", "jurisdictions": {
        "ZZ": {"status": "RESEARCH_ONLY_APPROVED", "human_legal_review": True,
               "reviewed_at": "2026-10-01T00:00:00Z",
               "expires_at": "2027-01-01T00:00:00Z",
               "reviewer": "Test counsel fixture",
               "checks": checks}}}


def parcel(parcel_id="ABC-123"):
    return {
        "jurisdiction": "ZZ", "county": "Example County", "parcel_id": parcel_id,
        "county_assessor_url": "https://assessor.example/parcel/ABC123",
        "county_recorder_url": "https://recorder.example/parcel/ABC123",
        "owner_identity_confidence": 0.8,
        "source": {"type": "county_assessor",
                   "record_url": "https://assessor.example/parcel/ABC123",
                   "terms_url": "https://assessor.example/terms",
                   "observed_at": "2026-10-27T18:00:00Z",
                   "collection_authorized": True, "terms_reviewed": True,
                   "robots_respected": True},
        "asking_price": 12000, "proposed_purchase_price": 11000,
        "acreage": 2.0, "days_listed": 10,
        "due_diligence": {
            "zoning": "Rural residential", "use_restrictions": [],
            "legal_road_access": True, "easements": [], "utilities": "unknown",
            "flood": "outside_mapped_floodplain", "wetlands": "not_identified",
            "unpaid_taxes": 0, "liens": 0,
            "title_evidence_url": "https://recorder.example/parcel/ABC123",
            "title_flags": [],
            "evidence_urls": ["https://assessor.example/parcel/ABC123",
                              "https://recorder.example/parcel/ABC123"]},
        "comps": [
            {"status": "closed_sale", "verified": True,
             "source_url": f"https://recorder.example/comp/{index}",
             "sale_date": "2026-08-01T00:00:00Z", "sale_price": price,
             "acreage": acreage, "distance_miles": distance}
            for index, (price, acreage, distance) in enumerate([
                (40000, 2.0, 5), (44000, 2.2, 8),
                (38000, 1.9, 12), (42000, 2.0, 15)])],
        "costs": {"closing": 1200, "due_diligence": 800,
                  "legal_assignment": 1000, "carrying_marketing": 500,
                  "taxes_liens": 0, "uncertainty_reserve": 2500},
        "buyer_intent": {"verified": False},
        "government_buyer_claim": False,
    }


class LandResearchTests(unittest.TestCase):
    def test_default_policy_is_quarantined(self):
        policy = land.load_policy()
        self.assertEqual(policy["jurisdictions"], {})
        result = land.evaluate(parcel(), policy, now=NOW)
        self.assertEqual(result["score"], 0)
        self.assertIn("jurisdiction_quarantined", result["hard_blocks"])

    def test_transparent_score_and_conservative_economics(self):
        result = land.evaluate(parcel(), approved_policy(), now=NOW)
        self.assertTrue(result["eligible_for_research_digest"])
        self.assertGreater(result["score"], 60)
        self.assertEqual(result["comp_analysis"]["valid_comp_count"], 4)
        self.assertLessEqual(result["comp_analysis"]["supported_sale_price"], 40000)
        self.assertEqual(result["economics"]["gross_spread"],
                         result["comp_analysis"]["supported_sale_price"] - 11000)
        self.assertEqual(result["economics"]["net_potential"],
                         result["economics"]["gross_spread"] - 6000)
        self.assertFalse(result["projected_value_is_revenue"])
        self.assertFalse(result["execution"]["outreach_allowed"])

    def test_duplicate_keeps_freshest_record(self):
        older = parcel("ABC 123")
        older["source"]["observed_at"] = "2026-10-20T00:00:00Z"
        report = land.digest([older, parcel("abc-123")], approved_policy(), now=NOW)
        self.assertEqual(report["deduplicated_count"], 1)
        self.assertEqual(report["duplicates"][0]["discarded_index"], 0)

    def test_misleading_active_listing_is_not_closed_comp(self):
        item = parcel()
        item["comps"] = [{"status": "active_listing", "verified": True,
                          "source_url": "https://listing.example/1",
                          "sale_date": "2026-08-01T00:00:00Z",
                          "sale_price": 72000, "acreage": 2, "distance_miles": 1}]
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertIn("no_verified_closed_comps", result["hard_blocks"])
        self.assertIn("not_closed_sale",
                      result["comp_analysis"]["rejected_comps"][0]["reasons"])

    def test_no_legal_road_access_hard_blocks(self):
        item = parcel()
        item["due_diligence"]["legal_road_access"] = False
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertIn("no_verified_legal_road_access", result["hard_blocks"])

    def test_missing_title_evidence_hard_blocks(self):
        item = parcel()
        item["due_diligence"]["title_evidence_url"] = None
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertIn("title_evidence_missing", result["hard_blocks"])

    def test_legal_market_disallow_is_quarantined(self):
        policy = approved_policy()
        policy["jurisdictions"]["ZZ"]["status"] = "DISALLOWED"
        result = land.evaluate(parcel(), policy, now=NOW)
        self.assertIn("jurisdiction_quarantined", result["hard_blocks"])

    def test_unsupported_government_buyer_claim_hard_blocks(self):
        item = parcel()
        item["government_buyer_claim"] = True
        item["buyer_intent"] = {"verified": True, "kind": "government",
                                "verified_at": "2026-10-27T19:00:00Z",
                                "evidence_url": "https://example.gov/program"}
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertIn("unsupported_government_buyer_claim", result["hard_blocks"])

    def test_verified_government_path_needs_procurement_evidence(self):
        item = parcel()
        item["government_buyer_claim"] = True
        item["buyer_intent"] = {"verified": True, "kind": "government",
                                "verified_at": "2026-10-27T19:00:00Z",
                                "evidence_url": "https://example.gov/notice",
                                "procurement_url": "https://example.gov/procurement/123",
                                "solicitation_id": "SOL-123"}
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertTrue(result["buyer_intent_verified"])
        self.assertNotIn("unsupported_government_buyer_claim", result["hard_blocks"])

    def test_stale_and_unauthorized_sources_fail_closed(self):
        item = parcel()
        item["source"]["observed_at"] = "2026-08-01T00:00:00Z"
        item["source"]["collection_authorized"] = False
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertIn("source_stale", result["hard_blocks"])
        self.assertIn("source_collection_not_authorized", result["hard_blocks"])

    def test_dry_run_never_counts_projection_as_revenue(self):
        report = land.digest([parcel()], approved_policy(), now=NOW)
        self.assertEqual(report["verified_settled_deals"], 0)
        self.assertEqual(report["verified_revenue_cents"], 0)
        self.assertEqual(report["projected_net_potential_cents"], 0)
        self.assertFalse(report["guardrails"]["outreach"])
        self.assertFalse(report["guardrails"]["contracts_or_signatures"])

    def test_only_evidence_backed_settlement_counts(self):
        unverified = parcel("X-1")
        unverified["settled"] = {"verified": False, "net_revenue_cents": 999999,
                                 "provider_transaction_id": "fake",
                                 "evidence_url": "https://closing.example/fake"}
        verified = parcel("X-2")
        verified["contract"] = {"externally_accepted": True,
                                "reviewed_for_jurisdiction": True,
                                "provider_contract_id": "contract-123",
                                "evidence_url": "https://closing.example/contract/123"}
        verified["settled"] = {"verified": True, "net_revenue_cents": 125000,
                               "provider_transaction_id": "closing-123",
                               "closing_provider": "Example Closing",
                               "currency": "USD",
                               "settled_at": "2026-10-27T19:30:00Z",
                               "evidence_url": "https://closing.example/receipt/123"}
        report = land.digest([unverified, verified], approved_policy(), now=NOW)
        self.assertEqual(report["verified_settled_deals"], 1)
        self.assertEqual(report["verified_revenue_cents"], 125000)

    def test_contract_and_settlement_lifecycle_is_separate(self):
        item = parcel()
        item["contract"] = {"externally_accepted": True,
                            "reviewed_for_jurisdiction": True,
                            "provider_contract_id": "contract-123",
                            "evidence_url": "https://closing.example/contract/123"}
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertEqual(result["stage"], "contract")
        self.assertTrue(result["lifecycle"]["contract_externally_accepted"])
        self.assertFalse(result["lifecycle"]["settled"])

    def test_low_owner_identity_confidence_fails_closed(self):
        item = parcel()
        item["owner_identity_confidence"] = 0.4
        result = land.evaluate(item, approved_policy(), now=NOW)
        self.assertIn("owner_identity_confidence_too_low", result["hard_blocks"])

    def test_cli_outputs_research_only_scorecard(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.json"
            policy = Path(tmp) / "policy.json"
            source.write_text(json.dumps({"parcels": [parcel()]}))
            policy.write_text(json.dumps(approved_policy()))
            run = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "land_research.py"),
                 str(source), "--policy", str(policy)], check=True,
                capture_output=True, text=True)
        result = json.loads(run.stdout)
        self.assertEqual(result["mode"], "research_only_dry_run")
        self.assertEqual(result["verified_revenue_cents"], 0)


if __name__ == "__main__":
    unittest.main()
