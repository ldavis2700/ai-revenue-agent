import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "lead_intake_pilot_readiness.py"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("lead_intake_pilot_readiness", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def valid_payload():
    path = ROOT / "templates" / "home_services_lead_intake_pilot_readiness.example.json"
    return json.loads(path.read_text(encoding="utf-8"))


class LeadIntakePilotReadinessTests(unittest.TestCase):
    def test_complete_funded_record_is_ready_for_owner_review_only(self):
        result = module.review(valid_payload())
        self.assertTrue(result["owner_review_ready"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["authorized_actions"], [])
        self.assertEqual(result["mastery"], "learned")
        self.assertEqual(result["collected_revenue_cents"], 0)

    def test_missing_consent_access_or_qa_fails_closed(self):
        payload = valid_payload()
        payload["consent_controls_verified"] = False
        payload["integration_authorized"] = False
        payload["qa_gates"]["rollback"] = False
        result = module.review(payload)
        self.assertFalse(result["owner_review_ready"])
        self.assertIn("consent_controls_verified_not_verified", result["blockers"])
        self.assertIn("integration_authorized_not_verified", result["blockers"])
        self.assertIn("qa_rollback_not_passed", result["blockers"])

    def test_unfunded_stage_cannot_be_ready(self):
        payload = valid_payload()
        payload["revenue_stage"] = "contract"
        payload["funding_evidence_ref"] = ""
        result = module.review(payload)
        self.assertIn("funded_billable_work_not_verified", result["blockers"])
        self.assertIn("funding_evidence_ref_missing", result["blockers"])

    def test_collection_requires_consistent_settled_evidence(self):
        payload = valid_payload()
        payload["revenue_stage"] = "collected_revenue"
        payload["collected_revenue_cents"] = 200000
        result = module.review(payload)
        self.assertIn("collected_stage_requires_settled_payment", result["blockers"])
        self.assertIn("collected_revenue_not_verified", result["blockers"])

        payload["settled_payment_verified"] = True
        result = module.review(payload)
        self.assertTrue(result["owner_review_ready"])
        self.assertEqual(result["collected_revenue_cents"], 200000)
        self.assertFalse(result["execution_authorized"])

    def test_settled_payment_cannot_precede_collection_stage(self):
        payload = valid_payload()
        payload["settled_payment_verified"] = True
        result = module.review(payload)
        self.assertIn("settled_payment_precedes_collected_stage", result["blockers"])

    def test_sensitive_data_fails_closed_without_echoing_value(self):
        payload = valid_payload()
        payload["unsafe"] = {"api_key": "private-value"}
        result = module.review(payload)
        self.assertIn("raw_secret_or_contact_data_detected", result["blockers"])
        self.assertNotIn("private-value", json.dumps(result))

    def test_cli_exit_codes_distinguish_ready_blocked_and_malformed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "readiness.json"
            path.write_text(json.dumps(valid_payload()), encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 0)
            blocked = valid_payload()
            blocked["contract_verified"] = False
            path.write_text(json.dumps(blocked), encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 1)
            path.write_text("not-json", encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 2)


if __name__ == "__main__":
    unittest.main()
