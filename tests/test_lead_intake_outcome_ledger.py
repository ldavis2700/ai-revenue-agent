import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "lead_intake_outcome_ledger.py"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("lead_intake_outcome_ledger", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def valid_payload():
    path = ROOT / "templates" / "home_services_lead_intake_outcome_ledger.example.json"
    return json.loads(path.read_text(encoding="utf-8"))


class LeadIntakeOutcomeLedgerTests(unittest.TestCase):
    def test_verified_event_produces_capped_review_estimate_only(self):
        result = module.audit(valid_payload())
        self.assertTrue(result["outcome_pricing_ready_for_owner_review"])
        self.assertEqual(result["eligible_event_count"], 1)
        self.assertEqual(result["estimated_outcome_fee_cents"], 2500)
        self.assertEqual(result["estimated_outcome_fee_status"], "review_only_not_billable")
        self.assertFalse(result["billing_authorized"])
        self.assertEqual(result["authorized_actions"], [])
        self.assertEqual(result["collected_revenue_cents"], 0)

    def test_fee_is_capped_without_becoming_billable(self):
        payload = valid_payload()
        base = payload["events"][0]
        payload["events"] = [{**base, "event_id": f"evt-{index}"} for index in range(20)]
        result = module.audit(payload)
        self.assertEqual(result["eligible_event_count"], 20)
        self.assertEqual(result["estimated_outcome_fee_cents"], 25000)
        self.assertFalse(result["billing_authorized"])

    def test_missing_paid_pilot_or_terms_fail_closed(self):
        payload = valid_payload()
        payload["pilot_settled_payment_verified"] = False
        payload["outcome_terms_accepted"] = False
        result = module.audit(payload)
        self.assertIn("pilot_settled_payment_verified_not_verified", result["blockers"])
        self.assertIn("outcome_terms_accepted_not_verified", result["blockers"])

    def test_duplicate_event_ids_are_blocked(self):
        payload = valid_payload()
        payload["events"].append(dict(payload["events"][0]))
        result = module.audit(payload)
        self.assertTrue(any(item.startswith("duplicate_event_id:") for item in result["blockers"]))
        self.assertEqual(result["eligible_event_count"], 1)

    def test_out_of_window_or_wrong_type_must_be_excluded(self):
        payload = valid_payload()
        payload["events"][0]["occurred_at"] = "2026-10-02T00:00:00Z"
        result = module.audit(payload)
        self.assertIn("event_0_outside_attribution_window_not_excluded", result["blockers"])

        payload = valid_payload()
        payload["events"][0]["event_type"] = "completed_job"
        result = module.audit(payload)
        self.assertIn("event_0_event_type_mismatch_not_excluded", result["blockers"])

    def test_disputed_event_requires_evidence_and_is_not_eligible(self):
        payload = valid_payload()
        payload["events"][0]["disputed"] = True
        result = module.audit(payload)
        self.assertIn("event_0_dispute_evidence_missing", result["blockers"])
        self.assertEqual(result["eligible_event_count"], 0)

        payload["events"][0]["dispute_evidence_ref"] = "redacted://buyer/dispute-001"
        result = module.audit(payload)
        self.assertTrue(result["outcome_pricing_ready_for_owner_review"])
        self.assertEqual(result["estimated_outcome_fee_cents"], 0)

    def test_sensitive_data_fails_closed_without_echoing_value(self):
        payload = valid_payload()
        payload["unsafe"] = {"customer_email": "person@example.com"}
        result = module.audit(payload)
        self.assertIn("raw_secret_or_contact_data_detected", result["blockers"])
        self.assertNotIn("person@example.com", json.dumps(result))

    def test_cli_exit_codes_distinguish_ready_blocked_and_malformed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(valid_payload()), encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 0)
            blocked = valid_payload()
            blocked["outcome_terms_accepted"] = False
            path.write_text(json.dumps(blocked), encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 1)
            path.write_text("not-json", encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 2)


if __name__ == "__main__":
    unittest.main()
