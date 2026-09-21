import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.notification_audit import (
    NotificationPlan,
    Severity,
    is_release_ready,
    main,
    plan_from_mapping,
    validate_plan,
)


class NotificationAuditTests(unittest.TestCase):
    def base_values(self, **overrides):
        values = {
            "name": "meetup reminder",
            "environment": "staging",
            "trigger": "meetup_start_minus_24h",
            "audience": "confirmed attendees",
            "exclusions": ["opted_out", "already_completed"],
            "deep_link": "app://meetups/123",
            "quiet_hours": "21:00-08:00 local",
            "frequency_cap": "1 per meetup per 24h",
            "success_metric": "attendance confirmation",
            "failure_metric": "delivery failure rate",
            "owner": "lifecycle",
            "consent_basis": "transactional app notification preference",
            "payload_sample": '{"meetup_id":"redacted"}',
        }
        values.update(overrides)
        return values

    def base(self, **overrides):
        values = self.base_values(**overrides)
        values["exclusions"] = tuple(values["exclusions"])
        return NotificationPlan(**values)

    def run_cli(self, payload, *args):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            if isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            else:
                path.write_text(json.dumps(payload), encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main([str(path), *args])
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_complete_plan_is_release_ready(self):
        self.assertEqual(validate_plan(self.base()), ())
        self.assertTrue(is_release_ready(self.base()))

    def test_blank_required_field_fails_closed(self):
        findings = validate_plan(self.base(trigger=""))
        self.assertIn(
            ("trigger", Severity.ERROR),
            {(finding.field, finding.severity) for finding in findings},
        )
        self.assertFalse(is_release_ready(self.base(trigger="")))

    def test_unknown_environment_is_error(self):
        findings = validate_plan(self.base(environment="live-ish"))
        self.assertTrue(
            any(
                finding.field == "environment"
                and finding.severity is Severity.ERROR
                for finding in findings
            )
        )

    def test_opt_out_suppression_is_mandatory(self):
        findings = validate_plan(self.base(exclusions=("already_completed",)))
        self.assertTrue(
            any(
                finding.field == "exclusions"
                and finding.severity is Severity.ERROR
                for finding in findings
            )
        )

    def test_invalid_deep_link_is_error(self):
        findings = validate_plan(self.base(deep_link="meetups/123"))
        self.assertTrue(
            any(
                finding.field == "deep_link"
                and finding.severity is Severity.ERROR
                for finding in findings
            )
        )

    def test_secret_like_payload_is_rejected(self):
        findings = validate_plan(self.base(payload_sample="Authorization: Bearer secret"))
        self.assertTrue(
            any(
                finding.field == "payload_sample"
                and finding.severity is Severity.ERROR
                for finding in findings
            )
        )

    def test_open_rate_only_is_warned_but_not_blocked(self):
        plan = self.base(success_metric="open rate")
        findings = validate_plan(plan)
        self.assertTrue(
            any(
                finding.field == "success_metric"
                and finding.severity is Severity.WARNING
                for finding in findings
            )
        )
        self.assertTrue(is_release_ready(plan))

    def test_cli_valid_json_is_release_ready(self):
        exit_code, stdout, stderr = self.run_cli(
            self.base_values(), "--format", "json"
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assertTrue(result["release_ready"])
        self.assertEqual(result["findings"], [])

    def test_cli_validation_error_returns_one(self):
        exit_code, stdout, stderr = self.run_cli(
            self.base_values(exclusions=["already_completed"]), "--format", "json"
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assertFalse(result["release_ready"])
        self.assertTrue(
            any(item["field"] == "exclusions" for item in result["findings"])
        )

    def test_cli_malformed_json_returns_two_without_traceback(self):
        exit_code, stdout, stderr = self.run_cli("{not json")
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("error: audit_file:", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_schema_rejects_unknown_fields(self):
        values = self.base_values(unexpected="value")
        with self.assertRaisesRegex(ValueError, "unknown field"):
            plan_from_mapping(values)

    def test_schema_rejects_non_string_exclusions(self):
        values = self.base_values(exclusions=["opted_out", 42])
        with self.assertRaisesRegex(ValueError, "array of strings"):
            plan_from_mapping(values)


if __name__ == "__main__":
    unittest.main()
