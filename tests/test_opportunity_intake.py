from datetime import datetime, timedelta, timezone
import json
import os
import sqlite3
import tempfile
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
    def proposal(self, **overrides):
        value = {
            "scope": "Build and validate the listed workflow automation.",
            "price_cents": 100000,
            "milestones": [{
                "title": "Validated implementation",
                "deliverable": "Tested workflow, deployment notes, and acceptance evidence.",
                "amount_cents": 100000,
                "due_days": 7,
            }],
            "claims": [{
                "text": "APEX has a tested opportunity and delivery ledger.",
                "source_url": "https://github.com/ldavis2700/ai-revenue-agent",
                "verified_at": NOW.isoformat(),
            }],
        }
        value.update(overrides)
        return value

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

    def test_persistence_is_idempotent_and_does_not_store_rejected_payload(self):
        accepted = candidate()
        rejected = candidate(external_id="bad", scam_signals=["advance fee"],
                             description="sensitive untrusted text")
        result = opportunity_intake.ingest([accepted, rejected], now=NOW)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            first = opportunity_intake.persist(result, path, now=NOW)
            second = opportunity_intake.persist(result, path, now=NOW + timedelta(minutes=1))
            connection = sqlite3.connect(path)
            opportunities = connection.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
            receipts = connection.execute("SELECT COUNT(*) FROM opportunity_receipts").fetchone()[0]
            stored = connection.execute("SELECT payload_json FROM opportunities").fetchone()[0]
            raw = " ".join(str(value) for row in connection.execute(
                "SELECT * FROM opportunity_receipts") for value in row)
            connection.close()
        self.assertEqual(first, {"opportunities_written": 1, "opportunities_unchanged": 0,
                                 "receipts_written": 2})
        self.assertEqual(second, {"opportunities_written": 0, "opportunities_unchanged": 1,
                                  "receipts_written": 0})
        self.assertEqual((opportunities, receipts), (1, 2))
        self.assertEqual(json.loads(stored)["external_id"], "job-123")
        self.assertNotIn("sensitive untrusted text", raw)

    def test_newer_observation_updates_and_older_observation_cannot_overwrite(self):
        older = candidate(title="Old", observed_at=(NOW - timedelta(hours=2)).isoformat())
        newer = candidate(title="New", observed_at=(NOW - timedelta(minutes=10)).isoformat())
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(opportunity_intake.ingest([older], now=NOW), path, now=NOW)
            update = opportunity_intake.persist(opportunity_intake.ingest([newer], now=NOW), path,
                                                now=NOW + timedelta(minutes=1))
            stale = opportunity_intake.persist(opportunity_intake.ingest([older], now=NOW), path,
                                               now=NOW + timedelta(minutes=2))
            connection = sqlite3.connect(path)
            title = connection.execute("SELECT title FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(update["opportunities_written"], 1)
        self.assertEqual(stale["opportunities_unchanged"], 1)
        self.assertEqual(title, "New")

    def test_persistence_rolls_back_partial_batch_on_error(self):
        result = opportunity_intake.ingest([candidate(), candidate(external_id="second")], now=NOW)
        del result["opportunities"][1]["source"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            with self.assertRaises(KeyError):
                opportunity_intake.persist(result, path, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
            receipt_count = connection.execute("SELECT COUNT(*) FROM opportunity_receipts").fetchone()[0]
            connection.close()
        self.assertEqual((count, receipt_count), (0, 0))

    def test_pipeline_transition_is_evidence_backed_and_idempotent(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            first = opportunity_intake.record_transition(
                path, opportunity_id, "qualified", "proposal_ready", "proposal:demo-v1", now=NOW)
            second = opportunity_intake.record_transition(
                path, opportunity_id, "qualified", "proposal_ready", "proposal:demo-v1", now=NOW)
            connection = sqlite3.connect(path)
            state, stored = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities").fetchone()
            transition = connection.execute(
                "SELECT from_state,to_state,evidence_id,evidence_hash FROM opportunity_transitions").fetchone()
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "proposal_ready")
        self.assertEqual(json.loads(stored)["pipeline_state"], "proposal_ready")
        self.assertEqual(transition[:3], ("qualified", "proposal_ready", "proposal:demo-v1"))
        self.assertEqual(len(transition[3]), 64)

    def test_pipeline_transition_rejects_skips_stale_state_and_missing_evidence(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            for expected, target, evidence, reason in (
                    ("qualified", "submitted", "provider/1", "transition_not_allowed"),
                    ("qualified", "proposal_ready", "", "transition_fields_required"),
                    ("qualified", "proposal_ready", "provider/1", "transition_evidence_invalid")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_transition(
                        path, opportunity_id, expected, target, evidence, now=NOW)
            opportunity_intake.record_transition(
                path, opportunity_id, "qualified", "proposal_ready", "proposal:1", now=NOW)
            with self.assertRaisesRegex(ValueError, "pipeline_state_conflict"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "qualified", "unqualified", "screen:2", now=NOW)

    def test_pipeline_transition_rolls_back_if_receipt_insert_fails(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_transition BEFORE INSERT ON opportunity_transitions
                                BEGIN SELECT RAISE(ABORT, 'receipt failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.record_transition(
                    path, opportunity_id, "qualified", "proposal_ready", "proposal:1", now=NOW)
            connection = sqlite3.connect(path)
            state = connection.execute(
                "SELECT pipeline_state FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()[0]
            connection.close()
        self.assertEqual(state, "qualified")

    def test_proposal_artifact_atomically_advances_and_is_idempotent(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            first = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            second = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            connection = sqlite3.connect(path)
            artifact = json.loads(connection.execute(
                "SELECT artifact_json FROM proposal_artifacts").fetchone()[0])
            state = connection.execute(
                "SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions").fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "proposal_ready")
        self.assertEqual(artifact["price_cents"], 100000)
        self.assertEqual(sum(x["amount_cents"] for x in artifact["milestones"]), 100000)
        self.assertEqual(evidence, "proposal:" + first["proposal_id"])

    def test_proposal_rejects_unpriced_unbalanced_or_unverified_content(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            invalid = [
                (self.proposal(price_cents=100001), "milestone_total_mismatch"),
                (self.proposal(price_cents=100001, milestones=[{
                    "title": "Too expensive", "deliverable": "Work",
                    "amount_cents": 100001, "due_days": 7,
                }]), "price_exceeds_opportunity_payout"),
                (self.proposal(claims=[{"text": "Unsupported"}]), "claim_source_url_required"),
                (self.proposal(claims=[{
                    "text": "Insecure evidence", "source_url": "http://example.com/proof",
                    "verified_at": NOW.isoformat(),
                }]), "claim_source_url_https_required"),
            ]
            for proposal, reason in invalid:
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.prepare_proposal(
                        path, opportunity_id, proposal, now=NOW)
            connection = sqlite3.connect(path)
            counts = (connection.execute("SELECT COUNT(*) FROM proposal_artifacts").fetchone()[0],
                      connection.execute("SELECT COUNT(*) FROM opportunity_transitions").fetchone()[0])
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(counts, (0, 0))
        self.assertEqual(state, "qualified")

    def test_proposal_rolls_back_if_transition_insert_fails(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_proposal_transition BEFORE INSERT
                                ON opportunity_transitions
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.prepare_proposal(
                    path, opportunity_id, self.proposal(), now=NOW)
            connection = sqlite3.connect(path)
            artifact_count = connection.execute(
                "SELECT COUNT(*) FROM proposal_artifacts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(artifact_count, 0)
        self.assertEqual(state, "qualified")

    def test_ranking_favors_close_ready_high_confidence_work(self):
        slow = candidate(external_id="slow", time_to_cash_days=60, execution_confidence=0.7,
                         buyer_intent=0.5, win_probability=0.4)
        fast = candidate(external_id="fast", time_to_cash_days=2, execution_confidence=0.95,
                         buyer_intent=0.95, win_probability=0.8)
        result = opportunity_intake.ingest([slow, fast], now=NOW)
        self.assertEqual(result["opportunities"][0]["external_id"], "fast")


if __name__ == "__main__":
    unittest.main()
