import unittest

from scripts.notification_audit import (
    NotificationPlan,
    Severity,
    is_release_ready,
    validate_plan,
)


class NotificationAuditTests(unittest.TestCase):
    def base(self, **overrides):
        values = {
            "name": "meetup reminder",
            "environment": "staging",
            "trigger": "meetup_start_minus_24h",
            "audience": "confirmed attendees",
            "exclusions": ("opted_out", "already_completed"),
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
        return NotificationPlan(**values)

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


if __name__ == "__main__":
    unittest.main()
