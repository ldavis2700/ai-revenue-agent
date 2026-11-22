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
        "outcome_pricing_requested": False,
        "economics": {
            "diagnostic_price_cents": 35000,
            "implementation_price_cents": 200000,
            "monthly_fee_cents": 90000,
            "initial_delivery_cost_cents": 40000,
            "monthly_delivery_cost_cents": 15000,
            "estimated_initial_api_cost_cents": 5000,
            "estimated_monthly_api_cost_cents": 5000,
            "estimated_cac_cents": 10000,
            "estimated_initial_human_hours": 8,
            "estimated_monthly_human_hours": 2,
        },
    }


class LeadIntakeQualificationTests(unittest.TestCase):
    def test_complete_evidence_is_eligible_for_scoping_only(self):
        result = module.qualify(valid_payload())
        self.assertTrue(result["eligible_for_scoping"])
        self.assertEqual(result["execution_gate"], "qualified_evidence_only")
        self.assertEqual(result["authorized_actions"], [])
        self.assertEqual(result["mastery"], "learned")
        self.assertEqual(result["economics"]["status"], "estimate_only")
        self.assertEqual(result["economics"]["initial_contribution_cents"], 180000)
        self.assertEqual(result["economics"]["monthly_contribution_cents"], 70000)
        self.assertEqual(result["economics"]["collected_revenue_cents"], 0)

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

    def test_outcome_pricing_is_blocked_until_verified_pilot_ledger(self):
        payload = valid_payload()
        payload["outcome_pricing_requested"] = True
        result = module.qualify(payload)
        self.assertFalse(result["eligible_for_scoping"])
        self.assertIn(
            "outcome_pricing_requires_verified_pilot_ledger", result["blockers"])
        self.assertEqual(
            result["outcome_pricing_gate"], "verified_pilot_ledger_required")

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

    def test_missing_economics_warns_without_inventing_values(self):
        payload = valid_payload()
        del payload["economics"]
        result = module.qualify(payload)
        self.assertTrue(result["eligible_for_scoping"])
        self.assertIn("economics_not_supplied_for_pricing", result["warnings"])
        self.assertNotIn("economics", result)

    def test_invalid_economics_block_and_out_of_band_prices_warn(self):
        payload = valid_payload()
        payload["economics"]["estimated_initial_human_hours"] = 0
        result = module.qualify(payload)
        self.assertFalse(result["eligible_for_scoping"])
        self.assertIn("estimated_initial_human_hours_invalid", result["blockers"])

        payload = valid_payload()
        payload["economics"]["diagnostic_price_cents"] = 10000
        result = module.qualify(payload)
        self.assertTrue(result["eligible_for_scoping"])
        self.assertIn("diagnostic_price_cents_outside_test_band", result["warnings"])

    def test_raw_credentials_and_customer_contacts_fail_closed_without_echoing_values(self):
        cases = (
            ("access_token", "opaque-value"),
            ("notes", "contact buyer@example.com"),
            ("notes", "call 562-555-0199"),
            ("notes", "Bearer abc.def.ghi"),
            ("notes", "sk_live_1234567890"),
        )
        for key, value in cases:
            with self.subTest(key=key, value=value):
                payload = valid_payload()
                payload["unsafe"] = {key: value}
                result = module.qualify(payload)
                serialized = json.dumps(result)
                self.assertFalse(result["eligible_for_scoping"])
                self.assertIn("raw_secret_or_contact_data_detected", result["blockers"])
                self.assertIn("redaction_blockers", result)
                self.assertNotIn(value, serialized)

    def test_redacted_evidence_references_and_authorization_fields_are_allowed(self):
        payload = valid_payload()
        payload["evidence_reference"] = "redacted://crm-export-2026-09"
        result = module.qualify(payload)
        self.assertTrue(result["eligible_for_scoping"])
        self.assertNotIn("redaction_blockers", result)

    def test_excessive_nesting_fails_closed(self):
        payload = valid_payload()
        nested = {}
        cursor = nested
        for _ in range(14):
            cursor["next"] = {}
            cursor = cursor["next"]
        payload["nested"] = nested
        result = module.qualify(payload)
        self.assertFalse(result["eligible_for_scoping"])
        self.assertIn("raw_secret_or_contact_data_detected", result["blockers"])
        self.assertTrue(any("nesting_too_deep" in path for path in result["redaction_blockers"]))

    def test_repository_example_is_redacted_and_eligible_for_scoping(self):
        path = ROOT / "templates" / "home_services_lead_intake_qualification.example.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = module.qualify(payload)
        self.assertTrue(result["eligible_for_scoping"])
        self.assertNotIn("redaction_blockers", result)
        self.assertEqual(result["outcome_pricing_gate"], "not_requested")

    def test_unprofitable_estimate_warns_but_is_not_recorded_as_revenue(self):
        payload = valid_payload()
        payload["economics"]["initial_delivery_cost_cents"] = 300000
        payload["economics"]["monthly_delivery_cost_cents"] = 100000
        result = module.qualify(payload)
        self.assertIn("initial_contribution_not_positive", result["warnings"])
        self.assertIn("monthly_contribution_not_positive", result["warnings"])
        self.assertEqual(result["economics"]["collected_revenue_cents"], 0)

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
