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


def submission_authorization(external_id="job-123", authorized_at=NOW):
    return {
        "submission_authorization_opportunity_id": opportunity_intake.stable_id(
            "permitted-marketplace", external_id, "https://example.com/jobs/123"),
        "submission_authorized_at": authorized_at.isoformat(),
    }


def spend_authorization(external_id="job-123", units=11, authorized_at=NOW):
    return {
        "application_spend_authorization_opportunity_id": (
            opportunity_intake.stable_id(
                "permitted-marketplace", external_id,
                "https://example.com/jobs/123")),
        "application_spend_authorized_units": units,
        "application_spend_authorized_at": authorized_at.isoformat(),
    }


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

    def advance_to_contract(self, path):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        opportunity_intake.persist(result, path, now=NOW)
        proposal = opportunity_intake.prepare_proposal(path, opportunity_id, self.proposal(), now=NOW)
        submitted = opportunity_intake.record_submission(path, opportunity_id, proposal["proposal_id"], {
            "provider": "marketplace", "external_submission_id": "application-456",
            "submission_url": "https://example.com/applications/456",
            "submitted_at": NOW.isoformat()}, now=NOW)
        replied = opportunity_intake.record_response(path, opportunity_id, submitted["receipt_id"], {
            "provider": "marketplace", "external_message_id": "message-789",
            "message_url": "https://example.com/messages/789",
            "received_at": NOW.isoformat()}, now=NOW)
        contracted = opportunity_intake.record_contract(path, opportunity_id, replied["receipt_id"], {
            "provider": "marketplace", "external_contract_id": "contract-321",
            "contract_url": "https://example.com/contracts/321",
            "amount_cents": 100000, "currency": "USD", "contracted_at": NOW.isoformat(),
            "terms_authority": "preapproved_standard_terms",
            "authority_evidence_url": "https://example.com/terms/standard-v1"}, now=NOW)
        return opportunity_id, contracted["receipt_id"]

    def advance_to_execution(self, path):
        opportunity_id, contract_id = self.advance_to_contract(path)
        execution = opportunity_intake.start_execution(path, opportunity_id, contract_id, {
            "execution_environment": "Isolated test environment", "started_at": NOW.isoformat(),
            "deliverables": [{"title": "Workflow", "description": "Build it.",
                              "acceptance_criteria": "Automated tests pass.",
                              "due_at": (NOW + timedelta(days=7)).isoformat()}]}, now=NOW)
        return opportunity_id, execution["plan_id"]

    def advance_to_qa(self, path):
        opportunity_id, plan_id = self.advance_to_execution(path)
        qa = opportunity_intake.pass_qa(path, opportunity_id, plan_id, {
            "artifact_sha256": "a" * 64, "completed_at": NOW.isoformat(),
            "tests": [{"name": "Acceptance suite", "status": "passed",
                       "evidence_url": "https://example.com/runs/123"}]}, now=NOW)
        return opportunity_id, qa["report_id"]

    def advance_to_delivery(self, path):
        opportunity_id, qa_id = self.advance_to_qa(path)
        delivery = opportunity_intake.record_delivery(path, opportunity_id, qa_id, {
            "provider": "marketplace", "external_delivery_id": "delivery-654",
            "delivery_url": "https://example.com/deliveries/654",
            "artifact_sha256": "a" * 64,
            "delivered_at": (NOW + timedelta(minutes=1)).isoformat()},
            now=NOW + timedelta(minutes=1))
        return opportunity_id, delivery["receipt_id"]

    def advance_to_invoice(self, path):
        opportunity_id, delivery_id = self.advance_to_delivery(path)
        invoice = opportunity_intake.record_invoice(path, opportunity_id, delivery_id, {
            "provider": "marketplace", "external_invoice_id": "invoice-987",
            "invoice_url": "https://example.com/invoices/987",
            "amount_cents": 100000, "currency": "USD",
            "issued_at": (NOW + timedelta(minutes=2)).isoformat(),
            "due_at": (NOW + timedelta(days=7)).isoformat()},
            now=NOW + timedelta(minutes=2))
        return opportunity_id, invoice["receipt_id"]

    def advance_to_collected(self, path):
        opportunity_id, invoice_id = self.advance_to_invoice(path)
        payment = opportunity_intake.record_collected_payment(
            path, opportunity_id, invoice_id, {
                "provider": "marketplace", "external_transaction_id": "payment-246",
                "transaction_url": "https://example.com/payments/246",
                "gross_amount_cents": 100000, "fee_amount_cents": 3000,
                "net_amount_cents": 97000, "currency": "USD",
                "paid_at": (NOW + timedelta(minutes=3)).isoformat(),
                "settled_at": (NOW + timedelta(minutes=4)).isoformat()},
            now=NOW + timedelta(minutes=4))
        return opportunity_id, payment["receipt_id"]

    def test_normalizes_and_scores_valid_candidate(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        item = result["opportunities"][0]
        self.assertEqual(item["url"], "https://example.com/jobs/123")
        self.assertEqual(item["currency"], "USD")
        self.assertGreater(item["score"], 0)
        self.assertEqual(item["action_mode"], "prepare_only")

    def test_autonomous_submit_requires_all_authorization_signals(self):
        item = candidate(platform_allows_automation=True, authenticated_channel=True,
                         submission_authorized=True,
                         **submission_authorization())
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["action_mode"], "autonomous_submit")
        item["requires_owner_identity"] = True
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["action_mode"], "prepare_only")

    def test_rejects_string_authorization_and_listing_flags(self):
        fields = [
            "payment_rail_clear",
            "platform_allows_automation",
            "authenticated_channel",
            "submission_authorized",
            "requires_deception",
            "requires_owner_identity",
            "unsolicited_direct_contact",
            "suppressed",
            "opted_out",
            "listing_open",
            "preferred_qualifications_met",
        ]
        values = [candidate(external_id=field, **{field: "false"}) for field in fields]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [f"{field}_invalid" for field in fields])

    def test_paid_submission_requires_specific_spend_authorization(self):
        item = candidate(
            platform_allows_automation=True,
            authenticated_channel=True,
            submission_authorized=True,
            **submission_authorization(),
            application_cost_units=11,
            application_units_balance=150,
            application_balance_observed_at=NOW.isoformat(),
        )
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["action_mode"], "prepare_only")
        item["application_spend_authorized"] = True
        item.update(spend_authorization())
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["action_mode"], "autonomous_submit")

    def test_application_spend_authorization_is_scoped_and_fresh(self):
        base = {
            "application_cost_units": 11,
            "application_units_balance": 150,
            "application_balance_observed_at": NOW.isoformat(),
            "application_spend_authorized": True,
        }
        values = [
            candidate(external_id="missing-spend-scope", **base),
            candidate(
                external_id="job-123",
                **base,
                **dict(spend_authorization(),
                       application_spend_authorization_opportunity_id="opp_wrong"),
            ),
            candidate(
                external_id="job-123",
                **base,
                **spend_authorization(units=12),
            ),
            candidate(
                external_id="job-123",
                **base,
                **spend_authorization(
                    authorized_at=NOW - timedelta(minutes=31)),
            ),
            candidate(
                external_id="job-123",
                **base,
                **spend_authorization(
                    authorized_at=NOW + timedelta(minutes=6)),
            ),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "application_spend_authorization_opportunity_id_required",
            "application_spend_authorization_opportunity_mismatch",
            "application_spend_authorized_units_mismatch",
            "application_spend_authorization_stale",
            "application_spend_authorized_at_future",
        ])

    def test_submission_authorization_is_fresh_and_opportunity_specific(self):
        values = [
            candidate(external_id="missing-authorization", submission_authorized=True),
            candidate(
                external_id="job-123",
                submission_authorized=True,
                submission_authorization_opportunity_id="opp_wrong",
                submission_authorized_at=NOW.isoformat(),
            ),
            candidate(
                external_id="job-123",
                submission_authorized=True,
                **submission_authorization(
                    authorized_at=NOW - timedelta(minutes=31)),
            ),
            candidate(
                external_id="job-123",
                submission_authorized=True,
                **submission_authorization(
                    authorized_at=NOW + timedelta(minutes=6)),
            ),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "submission_authorization_opportunity_id_required",
            "submission_authorization_opportunity_mismatch",
            "submission_authorization_stale",
            "submission_authorized_at_future",
        ])

    def test_rejects_paid_application_without_verified_sufficient_balance(self):
        values = [
            candidate(external_id="unknown-balance", application_cost_units=11),
            candidate(external_id="insufficient-balance", application_cost_units=11,
                      application_units_balance=10,
                      application_balance_observed_at=NOW.isoformat()),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "application_balance_unverified",
            "insufficient_application_units",
        ])

    def test_application_cost_lowers_rank_without_rejecting_funded_work(self):
        free = candidate(external_id="free", application_cost_units=0)
        paid = candidate(external_id="paid", application_cost_units=15,
                         application_units_balance=150,
                         application_balance_observed_at=NOW.isoformat())
        result = opportunity_intake.ingest([paid, free], now=NOW)
        self.assertEqual([item["external_id"] for item in result["opportunities"]],
                         ["free", "paid"])
        self.assertLess(result["opportunities"][1]["score_components"]["application_cost"], 0)

    def test_rejects_malformed_application_credit_evidence(self):
        values = [
            candidate(external_id="fractional-cost", application_cost_units=1.5,
                      application_units_balance=150),
            candidate(external_id="fractional-balance", application_cost_units=1,
                      application_units_balance=1.5),
            candidate(external_id="string-authorization",
                      application_spend_authorized="yes"),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "application_cost_units_invalid",
            "application_units_balance_invalid",
            "application_spend_authorized_invalid",
        ])

    def test_paid_application_requires_fresh_balance_evidence(self):
        values = [
            candidate(external_id="missing-timestamp", application_cost_units=11,
                      application_units_balance=150),
            candidate(external_id="stale-timestamp", application_cost_units=11,
                      application_units_balance=150,
                      application_balance_observed_at=(
                          NOW - timedelta(minutes=16)).isoformat()),
            candidate(external_id="future-timestamp", application_cost_units=11,
                      application_units_balance=150,
                      application_balance_observed_at=(
                          NOW + timedelta(minutes=6)).isoformat()),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "application_balance_observed_at_required",
            "application_balance_stale",
            "application_balance_observed_at_future",
        ])

    def test_submission_channel_outage_preserves_opportunity_without_autonomous_submit(self):
        item = candidate(platform_allows_automation=True, authenticated_channel=True,
                         submission_authorized=True,
                         **submission_authorization(),
                         submission_channel_status="temporarily_unavailable")
        accepted = opportunity_intake.ingest([item], now=NOW)["opportunities"][0]
        self.assertEqual(accepted["pipeline_state"], "qualified")
        self.assertEqual(accepted["action_mode"], "prepare_only")
        self.assertEqual(accepted["submission_channel_status"], "temporarily_unavailable")

    def test_rejects_unknown_submission_channel_status(self):
        result = opportunity_intake.ingest([
            candidate(submission_channel_status="broken-ish"),
        ], now=NOW)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["rejections"][0]["reason"],
                         "submission_channel_status_invalid")

    def test_rejects_conflicting_payment_rail_evidence(self):
        values = [
            candidate(external_id="false-clear", payment_rail_clear=False,
                      payment_rail_status="clear"),
            candidate(external_id="true-unavailable", payment_rail_clear=True,
                      payment_rail_status="temporarily_unavailable"),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "payment_rail_evidence_conflict",
            "payment_rail_evidence_conflict",
        ])

    def test_deduplicates_and_keeps_newest_observation(self):
        older = candidate(title="Older", url="https://example.com/jobs/123?old=true",
                          observed_at=(NOW - timedelta(hours=2)).isoformat())
        newer = candidate(title="Newer", url="https://example.com/jobs/123?new=true",
                          observed_at=(NOW - timedelta(minutes=10)).isoformat())
        result = opportunity_intake.ingest([older, newer], now=NOW)
        self.assertEqual([x["title"] for x in result["opportunities"]], ["Newer"])
        self.assertEqual(result["rejections"][0]["reason"], "duplicate_superseded")

    def test_newer_closed_duplicate_supersedes_stale_open_observation(self):
        older_open = candidate(
            observed_at=(NOW - timedelta(hours=2)).isoformat())
        newer_closed = candidate(
            observed_at=(NOW - timedelta(minutes=10)).isoformat(),
            listing_open=False)

        for observations in ([older_open, newer_closed],
                             [newer_closed, older_open]):
            with self.subTest(order=[item.get("listing_open", True)
                                     for item in observations]):
                result = opportunity_intake.ingest(observations, now=NOW)
                self.assertEqual(result["opportunities"], [])
                self.assertEqual(
                    {item["reason"] for item in result["rejections"]},
                    {"duplicate_superseded", "listing_closed"}
                    if observations[0].get("listing_open", True) else
                    {"listing_closed", "duplicate_older_or_equal"},
                )

    def test_equal_timestamp_terminal_duplicate_wins_in_any_arrival_order(self):
        open_item = candidate()
        closed_item = candidate(listing_open=False)

        for observations in ([open_item, closed_item],
                             [closed_item, open_item]):
            with self.subTest(order=[item.get("listing_open", True)
                                     for item in observations]):
                result = opportunity_intake.ingest(observations, now=NOW)
                self.assertEqual(result["opportunities"], [])
                self.assertEqual(
                    {item["reason"] for item in result["rejections"]},
                    {"listing_closed", "duplicate_superseded"}
                    if observations[0].get("listing_open", True) else
                    {"listing_closed", "duplicate_older_or_equal"},
                )

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

    def test_rejects_fractional_money_and_listing_counts(self):
        values = [
            candidate(external_id="fractional-payout", payout_cents=100000.5),
            candidate(external_id="fractional-positions", positions_to_hire=1.5),
            candidate(external_id="fractional-hires", hires_for_listing=0.5),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "payout_cents_invalid",
            "positions_to_hire_invalid",
            "hires_for_listing_invalid",
        ])

    def test_rejects_zero_pay_opportunity(self):
        result = opportunity_intake.ingest([
            candidate(external_id="unpaid", payout_cents=0),
        ], now=NOW)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["rejections"][0]["reason"],
                         "payout_cents_invalid")

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

    def test_rejects_closed_filled_and_profile_mismatched_marketplace_jobs(self):
        values = [
            candidate(external_id="closed", listing_open=False),
            candidate(external_id="filled", positions_to_hire=1, hires_for_listing=1),
            candidate(external_id="profile-mismatch", preferred_qualifications_met=False),
        ]
        result = opportunity_intake.ingest(values, now=NOW)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(
            [item["reason"] for item in result["rejections"]],
            ["listing_closed", "listing_filled", "preferred_qualifications_unmet"],
        )

    def test_unfilled_listing_and_met_qualifications_remain_eligible(self):
        result = opportunity_intake.ingest([
            candidate(positions_to_hire=2, hires_for_listing=1,
                      preferred_qualifications_met=True),
        ], now=NOW)
        self.assertEqual(len(result["opportunities"]), 1)

    def test_rejects_jobs_with_unavailable_execution_requirements(self):
        result = opportunity_intake.ingest([
            candidate(
                external_id="native-windows-excel",
                required_execution_capabilities=["windows_hardware", "native_excel"],
                available_execution_capabilities=["python", "libreoffice"],
            ),
        ], now=NOW)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["rejections"][0]["reason"],
                         "execution_capabilities_unmet")

    def test_accepts_explicitly_satisfied_execution_requirements(self):
        result = opportunity_intake.ingest([
            candidate(
                required_execution_capabilities=["playwright", "python", "playwright"],
                available_execution_capabilities=["python", "playwright", "sqlite"],
            ),
        ], now=NOW)
        item = result["opportunities"][0]
        self.assertEqual(item["required_execution_capabilities"],
                         ["playwright", "python"])
        self.assertEqual(item["missing_execution_capabilities"], [])

    def test_rejects_personal_data_collection_without_verified_authority(self):
        result = opportunity_intake.ingest([
            candidate(
                external_id="contact-harvesting",
                requires_personal_data_collection=True,
                personal_data_authorized=False,
            ),
        ], now=NOW)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["rejections"][0]["reason"],
                         "personal_data_authority_unverified")

    def test_accepts_authorized_personal_data_work_without_contacting_people(self):
        result = opportunity_intake.ingest([
            candidate(
                requires_personal_data_collection=True,
                personal_data_authorized=True,
                unsolicited_direct_contact=False,
            ),
        ], now=NOW)
        self.assertEqual(len(result["opportunities"]), 1)

    def test_rejects_raw_or_unclear_credential_access(self):
        values = [
            candidate(external_id="raw-login", requires_credential_access=True,
                      credential_access_method="raw"),
            candidate(external_id="unspecified-login", requires_credential_access=True),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, ["credential_access_unsafe", "credential_access_unsafe"])

    def test_accepts_provider_managed_credential_access(self):
        result = opportunity_intake.ingest([
            candidate(requires_credential_access=True,
                      credential_access_method="provider_managed"),
        ], now=NOW)
        self.assertEqual(len(result["opportunities"]), 1)

    def test_rejects_malformed_privacy_and_credential_evidence(self):
        values = [
            candidate(external_id="string-flag",
                      requires_personal_data_collection="false"),
            candidate(external_id="bad-credential-method",
                      requires_credential_access=True,
                      credential_access_method="email-me-a-password"),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "requires_personal_data_collection_invalid",
            "credential_access_method_invalid",
        ])

    def test_rejects_malformed_capability_evidence(self):
        values = [
            candidate(external_id="not-a-list",
                      required_execution_capabilities="windows_hardware"),
            candidate(external_id="empty-capability",
                      available_execution_capabilities=[""]),
            candidate(external_id="unsafe-capability",
                      required_execution_capabilities=["native excel / maybe"]),
        ]
        reasons = [item["reason"] for item in
                   opportunity_intake.ingest(values, now=NOW)["rejections"]]
        self.assertEqual(reasons, [
            "required_execution_capabilities_invalid",
            "available_execution_capabilities_invalid",
            "required_execution_capabilities_invalid",
        ])

    def test_temporary_payment_outage_preserves_pipeline_without_submission(self):
        item = candidate(payment_rail_clear=False, payment_rail_status="temporarily_unavailable",
                         platform_allows_automation=True, authenticated_channel=True,
                         submission_authorized=True,
                         **submission_authorization())
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

    def test_newer_terminal_rejection_invalidates_persisted_open_listing(self):
        older_open = candidate(
            observed_at=(NOW - timedelta(hours=2)).isoformat())
        newer_closed = candidate(
            observed_at=(NOW - timedelta(minutes=10)).isoformat(),
            listing_open=False)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            accepted = opportunity_intake.ingest([older_open], now=NOW)
            opportunity_intake.persist(accepted, path, now=NOW)
            rejected = opportunity_intake.ingest([newer_closed], now=NOW)
            update = opportunity_intake.persist(
                rejected, path, now=NOW + timedelta(minutes=1))
            connection = sqlite3.connect(path)
            state, observed_at, stored = connection.execute(
                "SELECT pipeline_state,observed_at,payload_json FROM opportunities"
            ).fetchone()
            transition = connection.execute(
                "SELECT from_state,to_state,evidence_id FROM opportunity_transitions"
            ).fetchone()
            connection.close()
        payload = json.loads(stored)
        self.assertEqual(update["opportunities_written"], 1)
        self.assertEqual(state, "unqualified")
        self.assertEqual(observed_at, newer_closed["observed_at"])
        self.assertEqual(payload["pipeline_state"], "unqualified")
        self.assertEqual(payload["observed_at"], newer_closed["observed_at"])
        self.assertEqual(payload["latest_screen_reason"], "listing_closed")
        self.assertEqual(transition[:2], ("qualified", "unqualified"))
        self.assertTrue(transition[2].startswith("screen:oppr_"))

    def test_known_expiration_retires_persisted_opportunity_without_new_observation(self):
        expiring = candidate(
            observed_at=(NOW - timedelta(hours=1)).isoformat(),
            expires_at=(NOW + timedelta(minutes=1)).isoformat())
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            accepted = opportunity_intake.ingest([expiring], now=NOW)
            opportunity_intake.persist(accepted, path, now=NOW)
            rejected = opportunity_intake.ingest(
                [expiring], now=NOW + timedelta(minutes=2))
            update = opportunity_intake.persist(
                rejected, path, now=NOW + timedelta(minutes=2))
            connection = sqlite3.connect(path)
            state, observed_at, stored = connection.execute(
                "SELECT pipeline_state,observed_at,payload_json FROM opportunities"
            ).fetchone()
            transition = connection.execute(
                "SELECT from_state,to_state,evidence_id FROM opportunity_transitions"
            ).fetchone()
            connection.close()
        payload = json.loads(stored)
        self.assertEqual(update["opportunities_written"], 1)
        self.assertEqual(state, "expired")
        self.assertEqual(observed_at, expiring["observed_at"])
        self.assertEqual(payload["pipeline_state"], "expired")
        self.assertEqual(payload["latest_screen_reason"], "opportunity_expired")
        self.assertEqual(transition[:2], ("qualified", "expired"))
        self.assertTrue(transition[2].startswith("expiry:oppr_"))

    def test_equal_timestamp_terminal_rejection_invalidates_persisted_listing(self):
        open_item = candidate()
        closed_item = candidate(listing_open=False)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(
                opportunity_intake.ingest([open_item], now=NOW), path, now=NOW)
            update = opportunity_intake.persist(
                opportunity_intake.ingest([closed_item], now=NOW), path,
                now=NOW + timedelta(minutes=1))
            connection = sqlite3.connect(path)
            state = connection.execute(
                "SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(update["opportunities_written"], 1)
        self.assertEqual(state, "unqualified")

    def test_terminal_rejection_does_not_regress_contracted_work(self):
        newer_closed = candidate(
            observed_at=(NOW + timedelta(minutes=1)).isoformat(),
            listing_open=False)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            self.advance_to_contract(path)
            rejected = opportunity_intake.ingest(
                [newer_closed], now=NOW + timedelta(minutes=1))
            update = opportunity_intake.persist(
                rejected, path, now=NOW + timedelta(minutes=2))
            connection = sqlite3.connect(path)
            state = connection.execute(
                "SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(update["opportunities_written"], 0)
        self.assertEqual(state, "contracted")

    def test_newer_observation_cannot_regress_an_advanced_pipeline_state(self):
        original = candidate(observed_at=(NOW - timedelta(hours=2)).isoformat())
        newer = candidate(title="Refreshed", observed_at=(NOW - timedelta(minutes=5)).isoformat())
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            result = opportunity_intake.ingest([original], now=NOW)
            opportunity_intake.persist(result, path, now=NOW)
            opportunity_id = result["opportunities"][0]["id"]
            opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            update = opportunity_intake.persist(
                opportunity_intake.ingest([newer], now=NOW), path,
                now=NOW + timedelta(minutes=1))
            connection = sqlite3.connect(path)
            state, stored, title = connection.execute(
                "SELECT pipeline_state,payload_json,title FROM opportunities").fetchone()
            connection.close()
        self.assertEqual(update["opportunities_written"], 1)
        self.assertEqual(state, "proposal_ready")
        self.assertEqual(json.loads(stored)["pipeline_state"], "proposal_ready")
        self.assertEqual(title, "Refreshed")

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
                path, opportunity_id, "qualified", "unqualified", "screen:buyer-withdrew", now=NOW)
            second = opportunity_intake.record_transition(
                path, opportunity_id, "qualified", "unqualified", "screen:buyer-withdrew", now=NOW)
            connection = sqlite3.connect(path)
            state, stored = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities").fetchone()
            transition = connection.execute(
                "SELECT from_state,to_state,evidence_id,evidence_hash FROM opportunity_transitions").fetchone()
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "unqualified")
        self.assertEqual(json.loads(stored)["pipeline_state"], "unqualified")
        self.assertEqual(transition[:3], ("qualified", "unqualified", "screen:buyer-withdrew"))
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
                    ("qualified", "proposal_ready", "proposal:1", "proposal_artifact_required")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_transition(
                        path, opportunity_id, expected, target, evidence, now=NOW)
            opportunity_intake.prepare_proposal(path, opportunity_id, self.proposal(), now=NOW)
            with self.assertRaisesRegex(ValueError, "submission_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "proposal_ready", "submitted", "submission:1", now=NOW)
            with self.assertRaisesRegex(ValueError, "pipeline_state_conflict"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "qualified", "expired", "expiry:2", now=NOW)

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
                    path, opportunity_id, "qualified", "unqualified", "screen:1", now=NOW)
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

    def test_submission_receipt_atomically_advances_and_is_idempotent(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        submission = {
            "provider": "Permitted Marketplace",
            "external_submission_id": "application-456",
            "submission_url": "HTTPS://EXAMPLE.COM/applications/456/",
            "submitted_at": NOW.isoformat(),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            prepared = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            first = opportunity_intake.record_submission(
                path, opportunity_id, prepared["proposal_id"], submission, now=NOW)
            second = opportunity_intake.record_submission(
                path, opportunity_id, prepared["proposal_id"], submission, now=NOW)
            connection = sqlite3.connect(path)
            receipt = connection.execute(
                "SELECT proposal_id,provider,submission_url,receipt_hash FROM submission_receipts"
            ).fetchone()
            state, stored = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities").fetchone()
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='submitted'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "submitted")
        self.assertEqual(json.loads(stored)["pipeline_state"], "submitted")
        self.assertEqual(receipt[0], prepared["proposal_id"])
        self.assertEqual(receipt[1], "Permitted Marketplace")
        self.assertEqual(receipt[2], "https://example.com/applications/456")
        self.assertEqual(len(receipt[3]), 64)
        self.assertEqual(evidence, "submission:" + first["receipt_id"])

    def test_submission_rejects_unproven_or_invalid_receipts(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        valid = {"provider": "marketplace", "external_submission_id": "application-456",
                 "submission_url": "https://example.com/applications/456",
                 "submitted_at": NOW.isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            with self.assertRaisesRegex(ValueError, "proposal_not_found"):
                opportunity_intake.record_submission(
                    path, opportunity_id, "prop_missing", valid, now=NOW)
            prepared = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            for changes, reason in (
                    ({"submission_url": "http://example.com/application"},
                     "submission_url_https_required"),
                    ({"submitted_at": (NOW + timedelta(minutes=6)).isoformat()},
                     "submitted_at_future")):
                invalid = dict(valid)
                invalid.update(changes)
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_submission(
                        path, opportunity_id, prepared["proposal_id"], invalid, now=NOW)
            connection = sqlite3.connect(path)
            receipt_count = connection.execute(
                "SELECT COUNT(*) FROM submission_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(receipt_count, 0)
        self.assertEqual(state, "proposal_ready")

    def test_submission_rolls_back_if_transition_insert_fails(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        submission = {"provider": "marketplace", "external_submission_id": "application-456",
                      "submission_url": "https://example.com/applications/456",
                      "submitted_at": NOW.isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            prepared = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_submission_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'submitted'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.record_submission(
                    path, opportunity_id, prepared["proposal_id"], submission, now=NOW)
            connection = sqlite3.connect(path)
            receipt_count = connection.execute(
                "SELECT COUNT(*) FROM submission_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(receipt_count, 0)
        self.assertEqual(state, "proposal_ready")

    def test_pipeline_receipts_reject_out_of_order_event_times(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            proposal = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            with self.assertRaisesRegex(ValueError, "submission_before_proposal"):
                opportunity_intake.record_submission(path, opportunity_id, proposal["proposal_id"], {
                    "provider": "marketplace", "external_submission_id": "application-early",
                    "submission_url": "https://example.com/applications/early",
                    "submitted_at": (NOW - timedelta(seconds=1)).isoformat()}, now=NOW)
            submitted = opportunity_intake.record_submission(
                path, opportunity_id, proposal["proposal_id"], {
                    "provider": "marketplace", "external_submission_id": "application-456",
                    "submission_url": "https://example.com/applications/456",
                    "submitted_at": NOW.isoformat()}, now=NOW)
            with self.assertRaisesRegex(ValueError, "response_before_submission"):
                opportunity_intake.record_response(path, opportunity_id, submitted["receipt_id"], {
                    "provider": "marketplace", "external_message_id": "message-early",
                    "message_url": "https://example.com/messages/early",
                    "received_at": (NOW - timedelta(seconds=1)).isoformat()}, now=NOW)
            replied = opportunity_intake.record_response(
                path, opportunity_id, submitted["receipt_id"], {
                    "provider": "marketplace", "external_message_id": "message-789",
                    "message_url": "https://example.com/messages/789",
                    "received_at": NOW.isoformat()}, now=NOW)
            with self.assertRaisesRegex(ValueError, "contract_before_response"):
                opportunity_intake.record_contract(path, opportunity_id, replied["receipt_id"], {
                    "provider": "marketplace", "external_contract_id": "contract-early",
                    "contract_url": "https://example.com/contracts/early",
                    "amount_cents": 100000, "currency": "USD",
                    "contracted_at": (NOW - timedelta(seconds=1)).isoformat(),
                    "terms_authority": "preapproved_standard_terms",
                    "authority_evidence_url": "https://example.com/terms/standard-v1"}, now=NOW)
            connection = sqlite3.connect(path)
            counts = (
                connection.execute("SELECT COUNT(*) FROM submission_receipts").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM response_receipts").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM contract_receipts").fetchone()[0])
            state = connection.execute(
                "SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(counts, (1, 1, 0))
        self.assertEqual(state, "response_received")

    def test_response_receipt_atomically_advances_and_is_idempotent(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        submission = {"provider": "marketplace", "external_submission_id": "application-456",
                      "submission_url": "https://example.com/applications/456",
                      "submitted_at": NOW.isoformat()}
        response = {"provider": "Marketplace", "external_message_id": "message-789",
                    "message_url": "HTTPS://EXAMPLE.COM/messages/789/",
                    "received_at": NOW.isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            proposal = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            submitted = opportunity_intake.record_submission(
                path, opportunity_id, proposal["proposal_id"], submission, now=NOW)
            first = opportunity_intake.record_response(
                path, opportunity_id, submitted["receipt_id"], response, now=NOW)
            second = opportunity_intake.record_response(
                path, opportunity_id, submitted["receipt_id"], response, now=NOW)
            connection = sqlite3.connect(path)
            receipt = connection.execute(
                "SELECT submission_receipt_id,message_url,receipt_hash FROM response_receipts"
            ).fetchone()
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='response_received'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "response_received")
        self.assertEqual(receipt[0], submitted["receipt_id"])
        self.assertEqual(receipt[1], "https://example.com/messages/789")
        self.assertEqual(len(receipt[2]), 64)
        self.assertEqual(evidence, "reply:" + first["receipt_id"])

    def test_response_rejects_unlinked_or_mismatched_provider_evidence(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        submission = {"provider": "marketplace", "external_submission_id": "application-456",
                      "submission_url": "https://example.com/applications/456",
                      "submitted_at": NOW.isoformat()}
        valid = {"provider": "marketplace", "external_message_id": "message-789",
                 "message_url": "https://example.com/messages/789",
                 "received_at": NOW.isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            proposal = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            submitted = opportunity_intake.record_submission(
                path, opportunity_id, proposal["proposal_id"], submission, now=NOW)
            with self.assertRaisesRegex(ValueError, "response_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "submitted", "response_received", "reply:free-form", now=NOW)
            with self.assertRaisesRegex(ValueError, "submission_receipt_not_found"):
                opportunity_intake.record_response(
                    path, opportunity_id, "subr_missing", valid, now=NOW)
            mismatch = dict(valid, provider="another-marketplace")
            with self.assertRaisesRegex(ValueError, "response_provider_mismatch"):
                opportunity_intake.record_response(
                    path, opportunity_id, submitted["receipt_id"], mismatch, now=NOW)
            insecure = dict(valid, message_url="http://example.com/messages/789")
            with self.assertRaisesRegex(ValueError, "message_url_https_required"):
                opportunity_intake.record_response(
                    path, opportunity_id, submitted["receipt_id"], insecure, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM response_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "submitted")

    def test_response_rolls_back_if_transition_insert_fails(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        submission = {"provider": "marketplace", "external_submission_id": "application-456",
                      "submission_url": "https://example.com/applications/456",
                      "submitted_at": NOW.isoformat()}
        response = {"provider": "marketplace", "external_message_id": "message-789",
                    "message_url": "https://example.com/messages/789",
                    "received_at": NOW.isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            proposal = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            submitted = opportunity_intake.record_submission(
                path, opportunity_id, proposal["proposal_id"], submission, now=NOW)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_response_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'response_received'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.record_response(
                    path, opportunity_id, submitted["receipt_id"], response, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM response_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "submitted")

    def test_contract_receipt_atomically_advances_and_is_idempotent(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        submission = {"provider": "marketplace", "external_submission_id": "application-456",
                      "submission_url": "https://example.com/applications/456",
                      "submitted_at": NOW.isoformat()}
        response = {"provider": "marketplace", "external_message_id": "message-789",
                    "message_url": "https://example.com/messages/789",
                    "received_at": NOW.isoformat()}
        contract = {"provider": "Marketplace", "external_contract_id": "contract-321",
                    "contract_url": "HTTPS://EXAMPLE.COM/contracts/321/",
                    "amount_cents": 100000, "currency": "usd",
                    "contracted_at": NOW.isoformat(),
                    "terms_authority": "preapproved_standard_terms",
                    "authority_evidence_url": "https://example.com/terms/standard-v1"}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            proposal = opportunity_intake.prepare_proposal(
                path, opportunity_id, self.proposal(), now=NOW)
            submitted = opportunity_intake.record_submission(
                path, opportunity_id, proposal["proposal_id"], submission, now=NOW)
            replied = opportunity_intake.record_response(
                path, opportunity_id, submitted["receipt_id"], response, now=NOW)
            first = opportunity_intake.record_contract(
                path, opportunity_id, replied["receipt_id"], contract, now=NOW)
            second = opportunity_intake.record_contract(
                path, opportunity_id, replied["receipt_id"], contract, now=NOW)
            connection = sqlite3.connect(path)
            receipt = connection.execute("""SELECT proposal_id,amount_cents,currency,
                terms_authority,contract_url,receipt_hash FROM contract_receipts""").fetchone()
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='contracted'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "contracted")
        self.assertEqual(receipt[:4], (proposal["proposal_id"], 100000, "USD",
                                      "preapproved_standard_terms"))
        self.assertEqual(receipt[4], "https://example.com/contracts/321")
        self.assertEqual(len(receipt[5]), 64)
        self.assertEqual(evidence, "contract:" + first["receipt_id"])

    def test_contract_rejects_unapproved_or_inconsistent_evidence(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            proposal = opportunity_intake.prepare_proposal(path, opportunity_id, self.proposal(), now=NOW)
            submitted = opportunity_intake.record_submission(path, opportunity_id, proposal["proposal_id"], {
                "provider": "marketplace", "external_submission_id": "application-456",
                "submission_url": "https://example.com/applications/456",
                "submitted_at": NOW.isoformat()}, now=NOW)
            replied = opportunity_intake.record_response(path, opportunity_id, submitted["receipt_id"], {
                "provider": "marketplace", "external_message_id": "message-789",
                "message_url": "https://example.com/messages/789",
                "received_at": NOW.isoformat()}, now=NOW)
            valid = {"provider": "marketplace", "external_contract_id": "contract-321",
                     "contract_url": "https://example.com/contracts/321",
                     "amount_cents": 100000, "currency": "USD",
                     "contracted_at": NOW.isoformat(),
                     "terms_authority": "preapproved_standard_terms",
                     "authority_evidence_url": "https://example.com/terms/standard-v1"}
            with self.assertRaisesRegex(ValueError, "contract_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "response_received", "contracted", "contract:free-form", now=NOW)
            for changes, reason in (
                    ({"terms_authority": "custom_terms"}, "terms_authority_invalid"),
                    ({"amount_cents": 100001}, "contract_amount_exceeds_proposal"),
                    ({"currency": "EUR"}, "contract_currency_mismatch"),
                    ({"provider": "other-provider"}, "contract_provider_mismatch")):
                invalid = dict(valid)
                invalid.update(changes)
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_contract(
                        path, opportunity_id, replied["receipt_id"], invalid, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM contract_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "response_received")

    def test_contract_rolls_back_if_transition_insert_fails(self):
        result = opportunity_intake.ingest([candidate()], now=NOW)
        opportunity_id = result["opportunities"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_intake.persist(result, path, now=NOW)
            proposal = opportunity_intake.prepare_proposal(path, opportunity_id, self.proposal(), now=NOW)
            submitted = opportunity_intake.record_submission(path, opportunity_id, proposal["proposal_id"], {
                "provider": "marketplace", "external_submission_id": "application-456",
                "submission_url": "https://example.com/applications/456",
                "submitted_at": NOW.isoformat()}, now=NOW)
            replied = opportunity_intake.record_response(path, opportunity_id, submitted["receipt_id"], {
                "provider": "marketplace", "external_message_id": "message-789",
                "message_url": "https://example.com/messages/789",
                "received_at": NOW.isoformat()}, now=NOW)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_contract_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'contracted'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.record_contract(path, opportunity_id, replied["receipt_id"], {
                    "provider": "marketplace", "external_contract_id": "contract-321",
                    "contract_url": "https://example.com/contracts/321",
                    "amount_cents": 100000, "currency": "USD",
                    "contracted_at": NOW.isoformat(),
                    "terms_authority": "owner_approved_terms",
                    "authority_evidence_url": "https://example.com/approvals/owner-1"}, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM contract_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "response_received")

    def test_execution_plan_atomically_advances_and_is_idempotent(self):
        plan = {"execution_environment": "Isolated repository branch and test environment",
                "started_at": NOW.isoformat(), "deliverables": [{
                    "title": "Validated workflow", "description": "Build the contracted automation.",
                    "acceptance_criteria": "Automated tests pass and deployment notes are complete.",
                    "due_at": (NOW + timedelta(days=7)).isoformat()}]}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, contract_id = self.advance_to_contract(path)
            first = opportunity_intake.start_execution(
                path, opportunity_id, contract_id, plan, now=NOW)
            second = opportunity_intake.start_execution(
                path, opportunity_id, contract_id, plan, now=NOW)
            connection = sqlite3.connect(path)
            artifact = json.loads(connection.execute(
                "SELECT plan_json FROM execution_plans").fetchone()[0])
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='executing'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "executing")
        self.assertEqual(artifact["contract_receipt_id"], contract_id)
        self.assertEqual(len(artifact["deliverables"]), 1)
        self.assertIn(first["plan_id"], evidence)

    def test_execution_plan_rejects_bypass_or_invalid_deliverables(self):
        valid = {"execution_environment": "Isolated test environment",
                 "started_at": NOW.isoformat(), "deliverables": [{
                     "title": "Workflow", "description": "Build it.",
                     "acceptance_criteria": "Tests pass.",
                     "due_at": (NOW + timedelta(days=7)).isoformat()}]}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, contract_id = self.advance_to_contract(path)
            with self.assertRaisesRegex(ValueError, "execution_plan_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "contracted", "executing", "contract:free-form", now=NOW)
            for plan, reason in (
                    (dict(valid, deliverables=[]), "deliverables_invalid"),
                    (dict(valid, deliverables=[{
                        "title": "Workflow", "description": "Build it.",
                        "acceptance_criteria": "Tests pass.",
                        "due_at": NOW.isoformat()}]), "deliverable_due_at_invalid"),
                    (dict(valid, started_at=(NOW + timedelta(minutes=6)).isoformat()),
                     "started_at_future"),
                    (dict(valid, started_at=(NOW - timedelta(seconds=1)).isoformat()),
                     "execution_before_contract")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.start_execution(
                        path, opportunity_id, contract_id, plan, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM execution_plans").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "contracted")

    def test_execution_plan_rolls_back_if_transition_insert_fails(self):
        plan = {"execution_environment": "Isolated test environment",
                "started_at": NOW.isoformat(), "deliverables": [{
                    "title": "Workflow", "description": "Build it.",
                    "acceptance_criteria": "Tests pass.",
                    "due_at": (NOW + timedelta(days=7)).isoformat()}]}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, contract_id = self.advance_to_contract(path)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_execution_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'executing'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.start_execution(
                    path, opportunity_id, contract_id, plan, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM execution_plans").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "contracted")

    def test_qa_report_atomically_advances_and_is_idempotent(self):
        report = {"artifact_sha256": "a" * 64, "completed_at": NOW.isoformat(),
                  "tests": [{"name": "Automated acceptance suite", "status": "passed",
                             "evidence_url": "HTTPS://EXAMPLE.COM/runs/123/"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, plan_id = self.advance_to_execution(path)
            first = opportunity_intake.pass_qa(path, opportunity_id, plan_id, report, now=NOW)
            second = opportunity_intake.pass_qa(path, opportunity_id, plan_id, report, now=NOW)
            connection = sqlite3.connect(path)
            artifact = json.loads(connection.execute(
                "SELECT report_json FROM qa_reports").fetchone()[0])
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='qa_passed'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "qa_passed")
        self.assertEqual(artifact["execution_plan_id"], plan_id)
        self.assertEqual(artifact["tests"][0]["evidence_url"], "https://example.com/runs/123")
        self.assertEqual(evidence, "qa:" + first["report_id"])

    def test_qa_rejects_bypass_failed_tests_and_weak_evidence(self):
        valid = {"artifact_sha256": "a" * 64, "completed_at": NOW.isoformat(),
                 "tests": [{"name": "Acceptance suite", "status": "passed",
                            "evidence_url": "https://example.com/runs/123"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, plan_id = self.advance_to_execution(path)
            with self.assertRaisesRegex(ValueError, "qa_report_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "executing", "qa_passed", "qa:free-form", now=NOW)
            for report, reason in (
                    (dict(valid, artifact_sha256="not-a-checksum"), "artifact_sha256_invalid"),
                    (dict(valid, tests=[{"name": "Acceptance suite", "status": "failed",
                                        "evidence_url": "https://example.com/runs/123"}]),
                     "qa_test_not_passed"),
                    (dict(valid, tests=[{"name": "Acceptance suite", "status": "passed",
                                        "evidence_url": "http://example.com/runs/123"}]),
                     "qa_evidence_url_https_required"),
                    (dict(valid, completed_at=(NOW - timedelta(seconds=1)).isoformat()),
                     "qa_before_execution")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.pass_qa(path, opportunity_id, plan_id, report, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM qa_reports").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "executing")

    def test_qa_rolls_back_if_transition_insert_fails(self):
        report = {"artifact_sha256": "a" * 64, "completed_at": NOW.isoformat(),
                  "tests": [{"name": "Acceptance suite", "status": "passed",
                             "evidence_url": "https://example.com/runs/123"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, plan_id = self.advance_to_execution(path)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_qa_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'qa_passed'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.pass_qa(path, opportunity_id, plan_id, report, now=NOW)
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM qa_reports").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "executing")

    def test_delivery_receipt_atomically_advances_and_is_idempotent(self):
        delivery = {"provider": "Marketplace", "external_delivery_id": "delivery-654",
                    "delivery_url": "HTTPS://EXAMPLE.COM/deliveries/654/",
                    "artifact_sha256": "a" * 64,
                    "delivered_at": (NOW + timedelta(minutes=1)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, qa_id = self.advance_to_qa(path)
            first = opportunity_intake.record_delivery(
                path, opportunity_id, qa_id, delivery, now=NOW + timedelta(minutes=1))
            second = opportunity_intake.record_delivery(
                path, opportunity_id, qa_id, delivery, now=NOW + timedelta(minutes=1))
            connection = sqlite3.connect(path)
            receipt = connection.execute(
                "SELECT qa_report_id,delivery_url,artifact_sha256,receipt_hash FROM delivery_receipts"
            ).fetchone()
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='delivered'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "delivered")
        self.assertEqual(receipt[0], qa_id)
        self.assertEqual(receipt[1], "https://example.com/deliveries/654")
        self.assertEqual(receipt[2], "a" * 64)
        self.assertEqual(len(receipt[3]), 64)
        self.assertEqual(evidence, "delivery:" + first["receipt_id"])

    def test_delivery_rejects_bypass_wrong_artifact_provider_or_timing(self):
        valid = {"provider": "marketplace", "external_delivery_id": "delivery-654",
                 "delivery_url": "https://example.com/deliveries/654",
                 "artifact_sha256": "a" * 64,
                 "delivered_at": (NOW + timedelta(minutes=1)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, qa_id = self.advance_to_qa(path)
            with self.assertRaisesRegex(ValueError, "delivery_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "qa_passed", "delivered", "delivery:free-form", now=NOW)
            for delivery, reason in (
                    (dict(valid, artifact_sha256="b" * 64), "delivery_artifact_mismatch"),
                    (dict(valid, provider="other-provider"), "delivery_provider_mismatch"),
                    (dict(valid, delivered_at=(NOW - timedelta(seconds=1)).isoformat()),
                     "delivered_before_qa"),
                    (dict(valid, delivery_url="http://example.com/deliveries/654"),
                     "delivery_url_https_required")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_delivery(
                        path, opportunity_id, qa_id, delivery, now=NOW + timedelta(minutes=1))
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM delivery_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "qa_passed")

    def test_delivery_rolls_back_if_transition_insert_fails(self):
        delivery = {"provider": "marketplace", "external_delivery_id": "delivery-654",
                    "delivery_url": "https://example.com/deliveries/654",
                    "artifact_sha256": "a" * 64,
                    "delivered_at": (NOW + timedelta(minutes=1)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, qa_id = self.advance_to_qa(path)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_delivery_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'delivered'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.record_delivery(
                    path, opportunity_id, qa_id, delivery, now=NOW + timedelta(minutes=1))
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM delivery_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "qa_passed")

    def test_invoice_receipt_atomically_advances_and_is_idempotent(self):
        invoice = {"provider": "Marketplace", "external_invoice_id": "invoice-987",
                   "invoice_url": "HTTPS://EXAMPLE.COM/invoices/987/",
                   "amount_cents": 100000, "currency": "usd",
                   "issued_at": (NOW + timedelta(minutes=2)).isoformat(),
                   "due_at": (NOW + timedelta(days=7)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, delivery_id = self.advance_to_delivery(path)
            first = opportunity_intake.record_invoice(
                path, opportunity_id, delivery_id, invoice, now=NOW + timedelta(minutes=2))
            second = opportunity_intake.record_invoice(
                path, opportunity_id, delivery_id, invoice, now=NOW + timedelta(minutes=2))
            connection = sqlite3.connect(path)
            receipt = connection.execute(
                "SELECT delivery_receipt_id,invoice_url,amount_cents,currency,receipt_hash FROM invoice_receipts"
            ).fetchone()
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='invoiced'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(state, "invoiced")
        self.assertEqual(receipt[:4], (delivery_id, "https://example.com/invoices/987", 100000, "USD"))
        self.assertEqual(len(receipt[4]), 64)
        self.assertEqual(evidence, "invoice:" + first["receipt_id"])

    def test_invoice_rejects_bypass_mismatch_and_invalid_timing(self):
        valid = {"provider": "marketplace", "external_invoice_id": "invoice-987",
                 "invoice_url": "https://example.com/invoices/987",
                 "amount_cents": 100000, "currency": "USD",
                 "issued_at": (NOW + timedelta(minutes=2)).isoformat(),
                 "due_at": (NOW + timedelta(days=7)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, delivery_id = self.advance_to_delivery(path)
            with self.assertRaisesRegex(ValueError, "invoice_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "delivered", "invoiced", "invoice:free-form", now=NOW)
            for invoice, reason in (
                    (dict(valid, amount_cents=100001), "invoice_amount_exceeds_contract"),
                    (dict(valid, currency="EUR"), "invoice_currency_mismatch"),
                    (dict(valid, provider="other-provider"), "invoice_provider_mismatch"),
                    (dict(valid, issued_at=NOW.isoformat()), "invoice_before_delivery"),
                    (dict(valid, due_at=(NOW + timedelta(minutes=2)).isoformat()), "due_at_invalid")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_invoice(
                        path, opportunity_id, delivery_id, invoice,
                        now=NOW + timedelta(minutes=2))
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM invoice_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "delivered")

    def test_invoice_rolls_back_if_transition_insert_fails(self):
        invoice = {"provider": "marketplace", "external_invoice_id": "invoice-987",
                   "invoice_url": "https://example.com/invoices/987",
                   "amount_cents": 100000, "currency": "USD",
                   "issued_at": (NOW + timedelta(minutes=2)).isoformat(),
                   "due_at": (NOW + timedelta(days=7)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, delivery_id = self.advance_to_delivery(path)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_invoice_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'invoiced'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.record_invoice(
                    path, opportunity_id, delivery_id, invoice,
                    now=NOW + timedelta(minutes=2))
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM invoice_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "delivered")

    def test_settled_payment_atomically_advances_and_is_idempotent(self):
        payment = {"provider": "Marketplace", "external_transaction_id": "payment-246",
                   "transaction_url": "HTTPS://EXAMPLE.COM/payments/246/",
                   "gross_amount_cents": 100000, "fee_amount_cents": 3000,
                   "net_amount_cents": 97000, "currency": "usd",
                   "paid_at": (NOW + timedelta(minutes=3)).isoformat(),
                   "settled_at": (NOW + timedelta(minutes=4)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, invoice_id = self.advance_to_invoice(path)
            first = opportunity_intake.record_collected_payment(
                path, opportunity_id, invoice_id, payment, now=NOW + timedelta(minutes=4))
            second = opportunity_intake.record_collected_payment(
                path, opportunity_id, invoice_id, payment, now=NOW + timedelta(minutes=4))
            connection = sqlite3.connect(path)
            receipt = connection.execute("""SELECT invoice_receipt_id,transaction_url,
                gross_amount_cents,fee_amount_cents,net_amount_cents,currency,receipt_hash
                FROM payment_receipts""").fetchone()
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            evidence = connection.execute(
                "SELECT evidence_id FROM opportunity_transitions WHERE to_state='collected'"
            ).fetchone()[0]
            connection.close()
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(first["net_amount_cents"], 97000)
        self.assertEqual(state, "collected")
        self.assertEqual(receipt[:6], (invoice_id, "https://example.com/payments/246",
                                      100000, 3000, 97000, "USD"))
        self.assertEqual(len(receipt[6]), 64)
        self.assertEqual(evidence, "verified_payment:" + first["receipt_id"])

    def test_payment_rejects_bypass_mismatches_and_unsettled_evidence(self):
        valid = {"provider": "marketplace", "external_transaction_id": "payment-246",
                 "transaction_url": "https://example.com/payments/246",
                 "gross_amount_cents": 100000, "fee_amount_cents": 3000,
                 "net_amount_cents": 97000, "currency": "USD",
                 "paid_at": (NOW + timedelta(minutes=3)).isoformat(),
                 "settled_at": (NOW + timedelta(minutes=4)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, invoice_id = self.advance_to_invoice(path)
            with self.assertRaisesRegex(ValueError, "payment_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "invoiced", "collected",
                    "verified_payment:free-form", now=NOW)
            for payment, reason in (
                    (dict(valid, gross_amount_cents=99999), "payment_net_amount_mismatch"),
                    (dict(valid, gross_amount_cents=99999, fee_amount_cents=2999),
                     "payment_amount_mismatch"),
                    (dict(valid, net_amount_cents=96000), "payment_net_amount_mismatch"),
                    (dict(valid, currency="EUR"), "payment_currency_mismatch"),
                    (dict(valid, provider="other-provider"), "payment_provider_mismatch"),
                    (dict(valid, transaction_url="http://example.com/payments/246"),
                     "transaction_url_https_required"),
                    (dict(valid, paid_at=NOW.isoformat()), "payment_before_invoice"),
                    (dict(valid, settled_at=(NOW + timedelta(minutes=2)).isoformat()),
                     "settled_before_paid")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_collected_payment(
                        path, opportunity_id, invoice_id, payment,
                        now=NOW + timedelta(minutes=4))
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM payment_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "invoiced")

    def test_payment_rolls_back_if_transition_insert_fails(self):
        payment = {"provider": "marketplace", "external_transaction_id": "payment-246",
                   "transaction_url": "https://example.com/payments/246",
                   "gross_amount_cents": 100000, "fee_amount_cents": 3000,
                   "net_amount_cents": 97000, "currency": "USD",
                   "paid_at": (NOW + timedelta(minutes=3)).isoformat(),
                   "settled_at": (NOW + timedelta(minutes=4)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, invoice_id = self.advance_to_invoice(path)
            connection = sqlite3.connect(path)
            connection.execute("""CREATE TRIGGER reject_payment_transition BEFORE INSERT
                                ON opportunity_transitions WHEN NEW.to_state = 'collected'
                                BEGIN SELECT RAISE(ABORT, 'transition failure'); END""")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                opportunity_intake.record_collected_payment(
                    path, opportunity_id, invoice_id, payment,
                    now=NOW + timedelta(minutes=4))
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM payment_receipts").fetchone()[0]
            state = connection.execute("SELECT pipeline_state FROM opportunities").fetchone()[0]
            connection.close()
        self.assertEqual(count, 0)
        self.assertEqual(state, "invoiced")

    def test_payout_lifecycle_distinguishes_collected_withdrawable_and_received(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, payment_id = self.advance_to_collected(path)
            payout_evidence = {
                "provider": "Marketplace", "external_balance_id": "balance-135",
                "evidence_url": "HTTPS://EXAMPLE.COM/balances/135/",
                "amount_cents": 97000, "currency": "usd",
                "available_at": (NOW + timedelta(minutes=5)).isoformat()}
            payout = opportunity_intake.record_withdrawable_balance(
                path, opportunity_id, payment_id, payout_evidence,
                now=NOW + timedelta(minutes=5))
            payout_again = opportunity_intake.record_withdrawable_balance(
                path, opportunity_id, payment_id, payout_evidence,
                now=NOW + timedelta(minutes=5))
            bank_evidence = {
                "financial_institution": "Provider-managed bank rail",
                "external_transfer_id": "transfer-864",
                "evidence_url": "https://example.com/transfers/864",
                "amount_cents": 97000, "currency": "USD",
                "received_at": (NOW + timedelta(minutes=6)).isoformat()}
            bank = opportunity_intake.record_bank_receipt(
                path, opportunity_id, payout["receipt_id"], bank_evidence,
                now=NOW + timedelta(minutes=6))
            bank_again = opportunity_intake.record_bank_receipt(
                path, opportunity_id, payout["receipt_id"], bank_evidence,
                now=NOW + timedelta(minutes=6))
            connection = sqlite3.connect(path)
            state = connection.execute(
                "SELECT pipeline_state FROM opportunities").fetchone()[0]
            transitions = connection.execute(
                "SELECT to_state,evidence_id FROM opportunity_transitions "
                "WHERE to_state IN ('withdrawable','received') ORDER BY recorded_at"
            ).fetchall()
            counts = (
                connection.execute(
                    "SELECT COUNT(*) FROM payout_availability_receipts").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM bank_receipts").fetchone()[0])
            connection.close()
        self.assertTrue(payout["changed"])
        self.assertFalse(payout_again["changed"])
        self.assertTrue(bank["changed"])
        self.assertFalse(bank_again["changed"])
        self.assertEqual(state, "received")
        self.assertEqual(counts, (1, 1))
        self.assertEqual(transitions, [
            ("withdrawable", "withdrawable_balance:" + payout["receipt_id"]),
            ("received", "bank_receipt:" + bank["receipt_id"]),
        ])

    def test_payout_lifecycle_rejects_bypass_and_mismatched_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "opportunities.db")
            opportunity_id, payment_id = self.advance_to_collected(path)
            with self.assertRaisesRegex(
                    ValueError, "withdrawable_balance_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "collected", "withdrawable",
                    "withdrawable_balance:free-form", now=NOW)
            valid = {
                "provider": "marketplace", "external_balance_id": "balance-135",
                "evidence_url": "https://example.com/balances/135",
                "amount_cents": 97000, "currency": "USD",
                "available_at": (NOW + timedelta(minutes=5)).isoformat()}
            for evidence, reason in (
                    (dict(valid, provider="other"), "payout_provider_mismatch"),
                    (dict(valid, amount_cents=96999), "payout_amount_mismatch"),
                    (dict(valid, currency="EUR"), "payout_currency_mismatch"),
                    (dict(valid, available_at=(NOW + timedelta(minutes=3)).isoformat()),
                     "withdrawable_before_settlement")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_withdrawable_balance(
                        path, opportunity_id, payment_id, evidence,
                        now=NOW + timedelta(minutes=5))
            payout = opportunity_intake.record_withdrawable_balance(
                path, opportunity_id, payment_id, valid,
                now=NOW + timedelta(minutes=5))
            with self.assertRaisesRegex(ValueError, "bank_receipt_required"):
                opportunity_intake.record_transition(
                    path, opportunity_id, "withdrawable", "received",
                    "bank_receipt:free-form", now=NOW)
            bank = {
                "financial_institution": "bank", "external_transfer_id": "transfer-864",
                "evidence_url": "https://example.com/transfers/864",
                "amount_cents": 97000, "currency": "USD",
                "received_at": (NOW + timedelta(minutes=6)).isoformat()}
            for evidence, reason in (
                    (dict(bank, amount_cents=96999), "bank_receipt_amount_mismatch"),
                    (dict(bank, currency="EUR"), "bank_receipt_currency_mismatch"),
                    (dict(bank, received_at=(NOW + timedelta(minutes=4)).isoformat()),
                     "bank_receipt_before_withdrawable")):
                with self.assertRaisesRegex(ValueError, reason):
                    opportunity_intake.record_bank_receipt(
                        path, opportunity_id, payout["receipt_id"], evidence,
                        now=NOW + timedelta(minutes=6))

    def test_ranking_favors_close_ready_high_confidence_work(self):
        slow = candidate(external_id="slow", time_to_cash_days=60, execution_confidence=0.7,
                         buyer_intent=0.5, win_probability=0.4)
        fast = candidate(external_id="fast", time_to_cash_days=2, execution_confidence=0.95,
                         buyer_intent=0.95, win_probability=0.8)
        result = opportunity_intake.ingest([slow, fast], now=NOW)
        self.assertEqual(result["opportunities"][0]["external_id"], "fast")


if __name__ == "__main__":
    unittest.main()
