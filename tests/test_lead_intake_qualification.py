import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lead_intake_qualification.py"
SPEC = importlib.util.spec_from_file_location("lead_intake_qualification", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def valid_payload():
    return {
        "monthly_inbound_leads": 60,
        "business_hours_missed_calls": 4,
        "after_hours_missed_calls": 12,
        "median_first_response_minutes": 45,
        "current_rates": {"contact": 0.7, "qualification": 0.6, "booking": 0.4,
                          "attendance": 0.8, "close": 0.5},
        "average_job_revenue_cents": 65000,
        "gross_profit_per_job_cents": 25000,
        "channels": ["phone", "sms", "email"],
        "crm_or_source_of_truth": "CRM export",
        "calendar_or_scheduler": "authorized scheduler",
        "consent_basis": "customer requested service through owned form or phone line",
        "opt_out_process_confirmed": True,
        "quiet_hours_defined": True,
        "suppression_list_available": True,
        "human_escalation_owner": "dispatch manager",
        "human_escalation_sla_minutes": 15,
        "authorized_integration_method": "scoped OAuth",
        "integration_authorized": True,
        "baseline_evidence": ["redacted CRM export", "call-log summary"],
        "uses_bought_or_scraped_lists": False,
        "emergency_dispatch_required": False,
        "guaranteed_outcome_requested": False,
    }


class LeadIntakeQualificationTests(unittest.TestCase):
    def test_complete_evidence_is_eligible_for_scoping_only(self):
        result = module.qualify(valid_payload())
        self.assertTrue(result["eligible_for_scoping"])
        self.assertEqual(result["execution_gate"], "qualified_evidence_only")
        self.assertEqual(result["authorized_actions"], [])
        self.assertEqual(result["mastery"], "learned")

    def test_missing_consent_and_suppression_fail_closed(self):
        payload = valid_payload()
        payload["consent_basis"] = ""
        payload["suppression_list_available"] = False
        result = module.qualify(payload)
        self.assertFalse(result["eligible_for_scoping"])
        self.assertIn("consent_basis_missing", result["blockers"])
        self.assertIn("suppression_list_available_not_confirmed", result["blockers"])

    def test_bought_lists_emergency_or_guarantee_are_blocked(self):
        for field in ("uses_bought_or_scraped_lists", "emergency_dispatch_required",
                      "guaranteed_outcome_requested"):
            with self.subTest(field=field):
                payload = valid_payload()
                payload[field] = True
                self.assertFalse(module.qualify(payload)["eligible_for_scoping"])

    def test_unknown_disqualifier_state_is_not_treated_as_false(self):
        payload = valid_payload()
        del payload["uses_bought_or_scraped_lists"]
        result = module.qualify(payload)
        self.assertIn("bought_or_scraped_list_status_not_disqualified", result["blockers"])

    def test_invalid_rates_and_economics_are_blocked(self):
        payload = valid_payload()
        payload["current_rates"]["booking"] = 1.1
        payload["gross_profit_per_job_cents"] = 70000
        result = module.qualify(payload)
        self.assertIn("current_rate_booking_invalid", result["blockers"])
        self.assertIn("gross_profit_exceeds_revenue", result["blockers"])

    def test_low_volume_is_warning_not_fabricated_disqualification(self):
        payload = valid_payload()
        payload["monthly_inbound_leads"] = 10
        result = module.qualify(payload)
        self.assertTrue(result["eligible_for_scoping"])
        self.assertIn("monthly_inbound_leads_below_target_icp", result["warnings"])

    def test_cli_exit_codes_distinguish_valid_blocked_and_malformed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(valid_payload()), encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 0)
            blocked = valid_payload()
            blocked["integration_authorized"] = False
            path.write_text(json.dumps(blocked), encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 1)
            path.write_text("not-json", encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(path)], check=False).returncode, 2)


if __name__ == "__main__":
    unittest.main()
