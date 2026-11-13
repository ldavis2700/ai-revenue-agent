import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.inherited_property_research import evaluate, persist


def valid():
    return {
        "parcel_id": "parcel-1", "source_url": "https://example.org/public-record",
        "source_date": "2026-11-13", "estate_related": True,
        "seller_authority_verified": True, "marketable_interest_verified": True,
        "closed_comps": [
            {"sold_price": 100000, "closed_date": "2026-09-01", "source_url": "https://example.org/a"},
            {"sold_price": 105000, "closed_date": "2026-10-01", "source_url": "https://example.org/b"},
        ],
        "supported_buyer_price": 100000, "purchase_price": 60000,
        "closing_costs": 5000, "repairs": 5000, "holding_costs": 2000,
        "buyer_margin": 10000, "uncertainty_reserve": 3000,
    }


def payload(record=None, cleared=True):
    from scripts.inherited_property_research import REQUIRED_CLEARANCE
    return {"jurisdiction": "synthetic test market",
            "jurisdiction_clearance": {key: cleared for key in REQUIRED_CLEARANCE},
            "records": [record if record is not None else valid()]}


class InheritedResearchTests(unittest.TestCase):
    def test_cleared_synthetic_lead_is_only_a_candidate_not_revenue(self):
        result = evaluate(payload())
        self.assertEqual(result["qualified"], 1)
        self.assertEqual(result["results"][0]["potential_fee"], 15000)
        self.assertEqual(result["collected_revenue"], 0)
        self.assertFalse(result["external_actions_allowed"])

    def test_jurisdiction_default_blocked(self):
        self.assertEqual(evaluate({"records": [valid()]})["qualified"], 0)

    def test_probate_authority_required(self):
        record = valid(); record["seller_authority_verified"] = False
        self.assertIn("estate_sale_authority_unverified",
                      evaluate(payload(record))["results"][0]["reasons"])

    def test_unverified_equity_cannot_replace_closed_comps(self):
        record = valid(); record["closed_comps"] = []
        record["estimated_equity"] = 5000000
        self.assertEqual(evaluate(payload(record))["qualified"], 0)

    def test_marketability_required(self):
        record = valid(); record["marketable_interest_verified"] = False
        self.assertIn("no_marketable_interest",
                      evaluate(payload(record))["results"][0]["reasons"])

    def test_reject_negative_margin(self):
        record = valid(); record["purchase_price"] = 100000
        self.assertIn("nonpositive_downside_margin",
                      evaluate(payload(record))["results"][0]["reasons"])

    def test_duplicates_are_not_double_counted(self):
        data = payload(); data["records"].append(valid())
        result = evaluate(data)
        self.assertEqual(result["qualified"], 1)
        self.assertEqual(result["results"][1]["reasons"], ["duplicate_parcel"])

    def test_idempotent_day_in_existing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "apex.db")
            report = evaluate(payload())
            persist(db, "2026-11-13", report)
            persist(db, "2026-11-13", report)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute("select count(*) from model_research_daily").fetchone()[0], 1)
                saved = json.loads(conn.execute("select report_json from model_research_daily").fetchone()[0])
                self.assertEqual(saved["collected_revenue"], 0)


if __name__ == "__main__":
    unittest.main()
