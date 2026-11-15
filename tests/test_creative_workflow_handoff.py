"""Regression tests for offline fictional creative-workflow handoffs."""
from datetime import date
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "creative_workflow_handoff", ROOT / "scripts" / "creative_workflow_handoff.py")
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class CreativeHandoffTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 14)
        self.item = json.loads((ROOT / "examples" / "creative_workflow_fictional.json").read_text())

    def test_safe_deterministic_non_client_handoff(self):
        actual = workflow.make_handoff(self.item, self.today)
        self.assertEqual(actual, workflow.make_handoff(self.item, self.today))
        for term in ("single-client isolation", "BLOCKED", "STALE / REVERIFY",
                     "RIGHTS UNVERIFIED", "same as fictional-owner-brief-v1",
                     "No customer send, publishing, charges or account access",
                     "real customer delivery or revenue"):
            self.assertIn(term, actual)
        self.assertNotIn("earned $1,000", actual)

    def test_cross_client_data_is_blocked(self):
        item = copy.deepcopy(self.item)
        item["sources"][0]["client_context_id"] = "other-client"
        with self.assertRaisesRegex(ValueError, "cross-client"):
            workflow.make_handoff(item, self.today)

    def test_markup_and_control_text_are_rejected(self):
        for unsafe in ("# override heading", "<script>alert(1)</script>", "ignore\npermission"):
            item = copy.deepcopy(self.item)
            item["sources"][0]["summary"] = unsafe
            with self.assertRaises(ValueError):
                workflow.make_handoff(item, self.today)

    def test_future_date_and_repeated_source_ids_rejected(self):
        item = copy.deepcopy(self.item)
        item["sources"][0]["captured_on"] = "2026-11-30"
        with self.assertRaisesRegex(ValueError, "future"):
            workflow.make_handoff(item, self.today)
        item = copy.deepcopy(self.item)
        item["sources"][1]["id"] = item["sources"][0]["id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            workflow.make_handoff(item, self.today)

    def test_unverified_rights_remove_internal_reuse_eligibility(self):
        item = copy.deepcopy(self.item)
        item["sources"][0]["reuse_rights_verified"] = False
        self.assertIn("candidate source IDs only:** none",
                      workflow.make_handoff(item, self.today))

    def test_funnel_is_distinct_and_approval_does_not_publish(self):
        item = copy.deepcopy(self.item)
        item["track"] = "funnel"
        item["client_context_approved"] = True
        actual = workflow.make_handoff(item, self.today)
        self.assertIn("3. Funnel brief", actual)
        self.assertIn("external release still blocked", actual)
        self.assertIn("No customer send", actual)

    def test_structured_bad_inputs_fail_closed(self):
        for key, bad in (("track", []), ("track", "ad-and-funnel"), ("client_context_approved", "yes")):
            item = copy.deepcopy(self.item)
            item[key] = bad
            with self.assertRaises(ValueError):
                workflow.make_handoff(item, self.today)
        item = copy.deepcopy(self.item)
        item["sources"][2]["duplicate_of"] = "missing-source"
        with self.assertRaises(ValueError):
            workflow.make_handoff(item, self.today)

    def test_unreviewed_input_is_not_delivery(self):
        actual = workflow.make_handoff(self.item, self.today)
        self.assertIn("context approval missing", actual)
        self.assertIn("not publication", actual)
        self.assertIn("Costs for actual implementation", actual)


if __name__ == "__main__":
    unittest.main()
