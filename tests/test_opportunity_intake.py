from datetime import datetime, timedelta, timezone
import unittest

from scripts import opportunity_intake


NOW = datetime(2026, 9, 8, 4, 0, tzinfo=timezone.utc)


def candidate(**overrides):
    value = {
        "source": "permitted-marketplace",
        "external_id": "job-123",
        "url": "HTTPS://EXAMPLE.COM/jobs/123/",
        "title": "Build a workflow automation",
        "observed_at": (NOW - timedelta(hours=1)).isoformat(),
        "expires_at": (NOW + timedelta(days=7)).isoformat(),
        "payout_cents": 100000,
        "currency": "usd",
        "effort_hours": 10,
        "time_to_cash_days": 7,
        "buyer_intent": 0.9,
        "win_probability": 0.7,
        "execution_confidence": 0.95,
        "payment_risk": 0.1,
        "reuse_value": 0.8,
        "recurring_value": 0.4,
        "payment_rail_clear": True,
    }
    value.update(overrides)
    return value


class OpportunityIntakeTests(unittest.TestCase):
    def test_normalizes_and_scores_valid_candidate(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        item = result["opportunities"][0]
        self.assertEqual(item["url"], "https://example.com/jobs/123")
        self.assertEqual(item["currency"], "USD")
        self.assertGreater(item["score"], 0)
        self.assertEqual(item["action_mode"], "prepare_only")

    def test_autonomous_submit_requires_all_authorization_signals(self):
        item = candidate(platform_allows_automation=True, authenticated_channel=True,
                         submission_authorized=True)
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["action_mode"], "autonomous_submit")
        item["requires_owner_identity"] = True
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["action_mode"], "prepare_only")

    def test_deduplicates_and_keeps_newest_observation(self):
        older = candidate(title="Older", url="https://example.com/jobs/123?old=true",
                          observed_at=(NOW - timedelta(hours=2)).isoformat())
        newer = candidate(title="Newer", url="https://example.com/jobs/123?new=true",
                          observed_at=(NOW - timedelta(minutes=10)).isoformat())
        result = opportunity_intake.ingest([older, newer], now=NOW)
        self.assertEqual([x["title"] for x in result["opportunities"]], ["Newer"])
        self.assertEqual(result["rejections"][0]["reason"], "duplicate_superseded")

    def test_rejects_stale_expired_and_future_observations(self):
        values = [
            candidate(external_id="stale", observed_at=(NOW - timedelta(days=31)).isoformat()),
            candidate(external_id="expired", expires_at=(NOW - timedelta(seconds=1)).isoformat()),
            candidate(external_id="future", observed_at=(NOW + timedelta(minutes=6)).isoformat()),
        ]
        reasons = {x["reason"] for x in opportunity_intake.ingest(values, now=NOW)["rejections"]}
        self.assertEqual(reasons, {"opportunity_stale", "opportunity_expired", "observed_at_future"})

    def test_rejects_non_finite_and_out_of_range_numbers(self):
        values = [candidate(external_id="nan", payout_cents=float("nan")),
                  candidate(external_id="prob", win_probability=1.1)]
        reasons = [x["reason"] for x in opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, ["payout_cents_invalid", "win_probability_invalid"])

    def test_hard_rejects_risk_and_policy_failures(self):
        values = [
            candidate(external_id="fraud", prohibited_category="fraud"),
            candidate(external_id="scam", scam_signals=["advance fee"]),
            candidate(external_id="deception", requires_deception=True),
            candidate(external_id="cold", unsolicited_direct_contact=True),
            candidate(external_id="suppressed", suppressed=True),
            candidate(external_id="rail", payment_rail_clear=False),
            candidate(external_id="capability", execution_confidence=0.59),
        ]
        reasons = [x["reason"] for x in opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, ["prohibited_category", "scam_signals_present", "deception_required",
                                   "unsolicited_contact_disallowed", "suppressed_or_opted_out",
                                   "payment_rail_unclear", "execution_confidence_too_low"])

    def test_temporary_payment_outage_preserves_pipeline_without_submission(self):
        item = candidate(payment_rail_clear=False, payment_rail_status="temporarily_unavailable",
                         platform_allows_automation=True, authenticated_channel=True,
                         submission_authorized=True)
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["pipeline_state"], "payment_rail_blocked")
        self.assertEqual(accepted["action_mode"], "prepare_only")

    def test_ranking_favors_close_ready_high_confidence_work(self):
        slow = candidate(external_id="slow", time_to_cash_days=60, execution_confidence=0.7,
                         buyer_intent=0.5, win_probability=0.4)
        fast = candidate(external_id="fast", time_to_cash_days=2, execution_confidence=0.95,
                         buyer_intent=0.95, win_probability=0.8)
        result = opportunity_intake.ingest([slow, fast], now=NOW)
        self.assertEqual(result["opportunities"][0]["external_id"], "fast")


if __name__ == "__main__":
    unittest.main()
