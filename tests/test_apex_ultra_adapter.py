import io
import json
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from apex_ultra_adapter import (
    HandoffError,
    build_payload,
    make_idempotency_key,
    submit_handoff,
)


class Response:
    status = 202
    headers = {"Content-Type": "application/json; charset=utf-8"}

    def __init__(self, body):
        self.stream = io.BytesIO(json.dumps(body).encode())
        self.closed = False

    def read(self, size=-1):
        return self.stream.read(size)

    def close(self):
        self.closed = True


class ApexUltraAdapterTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "business_case_id": "revenue-case-0042",
            "project": "APEX",
            "goal": "Plan a verified paid-service fulfillment improvement",
            "requested_capabilities": ["preview_verification", "plan"],
        }
        self.env = patch.dict(os.environ, {
            "APEX_ULTRA_HANDOFF_ENABLED": "true",
            "APEX_ULTRA_URL": "https://ultra.example.test",
            "APEX_ULTRA_ALLOWED_HOST": "ultra.example.test",
            "APEX_ULTRA_API_TOKEN": "a-long-private-test-token",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def response_body(self, payload, **overrides):
        body = {
            "id": "request-1",
            "task_id": "task-1",
            "origin": payload["origin"],
            "business_case_id": payload["business_case_id"],
            "project": payload["project"],
            "goal": payload["goal"],
            "requested_capabilities": payload["requested_capabilities"],
            "status": "queued",
            "deduplicated": False,
            "execution_authorized": False,
            "production_authorized": False,
            "outreach_authorized": False,
        }
        body.update(overrides)
        return body

    def assert_reason(self, reason, **changes):
        case = {**self.case, **changes}
        with self.assertRaisesRegex(HandoffError, "^" + reason + "$"):
            build_payload(**case)

    def test_stable_key_and_sorted_capabilities(self):
        first = make_idempotency_key(**self.case)
        second = make_idempotency_key(**{
            **self.case,
            "requested_capabilities": list(reversed(
                self.case["requested_capabilities"])),
        })
        self.assertEqual(first, second)
        payload = build_payload(**self.case)
        self.assertEqual(payload["requested_capabilities"],
                         ["plan", "preview_verification"])

    def test_request_validation_fails_closed(self):
        self.assert_reason("project_not_allowlisted", project="OTHER")
        self.assert_reason("goal_length_invalid", goal="short")
        self.assert_reason("business_case_id_invalid", business_case_id="bad")
        self.assert_reason("requested_capability_count_invalid",
                           requested_capabilities=[])
        self.assert_reason("requested_capabilities_duplicate",
                           requested_capabilities=["plan", "plan"])
        self.assert_reason("requested_capability_not_allowlisted",
                           requested_capabilities=["production"])

    def test_disabled_or_unsafe_configuration_is_blocked(self):
        payload = build_payload(**self.case)
        transport = lambda req, timeout: Response(self.response_body(payload))
        scenarios = [
            ({"APEX_ULTRA_HANDOFF_ENABLED": "false"}, "handoff_disabled"),
            ({"APEX_ULTRA_URL": "http://ultra.example.test"},
             "authenticated_https_endpoint_required"),
            ({"APEX_ULTRA_URL": "https://user@ultra.example.test"},
             "authenticated_https_endpoint_required"),
            ({"APEX_ULTRA_ALLOWED_HOST": "other.example.test"},
             "endpoint_host_not_allowlisted"),
            ({"APEX_ULTRA_API_TOKEN": "short"}, "api_token_required"),
        ]
        for env, reason in scenarios:
            with self.subTest(reason=reason), patch.dict(os.environ, env):
                with self.assertRaisesRegex(HandoffError, "^" + reason + "$"):
                    submit_handoff(**self.case, transport=transport)

    def test_submission_uses_exact_endpoint_auth_and_idempotency(self):
        seen = {}

        def transport(request, timeout):
            seen["url"] = request.full_url
            seen["headers"] = dict(request.header_items())
            seen["payload"] = json.loads(request.data)
            seen["timeout"] = timeout
            return Response(self.response_body(seen["payload"]))

        result = submit_handoff(**self.case, transport=transport)
        self.assertEqual(seen["url"],
                         "https://ultra.example.test/orchestration/requests")
        self.assertEqual(seen["headers"]["Authorization"],
                         "Bearer a-long-private-test-token")
        self.assertEqual(seen["headers"]["Idempotency-key"],
                         seen["payload"]["idempotency_key"])
        self.assertEqual(seen["timeout"], 20)
        self.assertFalse(result["execution_authorized"])

    def test_authority_or_identity_escalation_is_rejected(self):
        payload = build_payload(**self.case)
        scenarios = [
            ({"production_authorized": True},
             "provider_response_authority_unsafe"),
            ({"outreach_authorized": None},
             "provider_response_authority_unsafe"),
            ({"project": "HAEVEN"},
             "provider_response_identity_mismatch"),
            ({"status": "executed"}, "provider_response_status_invalid"),
        ]
        for changes, reason in scenarios:
            with self.subTest(reason=reason):
                transport = lambda req, timeout, changes=changes: Response(
                    self.response_body(payload, **changes))
                with self.assertRaisesRegex(HandoffError, "^" + reason + "$"):
                    submit_handoff(**self.case, transport=transport)

    def test_verified_receipt_is_persisted_without_token_or_goal(self):
        payload = build_payload(**self.case)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "receipts.db")
            transport = lambda req, timeout: Response(
                self.response_body(payload))
            submit_handoff(**self.case, receipt_db_path=path,
                           transport=transport)
            with sqlite3.connect(path) as db:
                columns = [row[1] for row in db.execute(
                    "PRAGMA table_info(apex_ultra_handoff_receipts)")]
                row = db.execute(
                    "SELECT request_id,task_id,status FROM "
                    "apex_ultra_handoff_receipts").fetchone()
            self.assertNotIn("token", " ".join(columns).lower())
            self.assertNotIn("goal", columns)
            self.assertEqual(row, ("request-1", "task-1", "queued"))

    def test_replayed_handoff_cannot_replace_recorded_provider_identity(self):
        payload = build_payload(**self.case)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "receipts.db")
            submit_handoff(
                **self.case, receipt_db_path=path,
                transport=lambda req, timeout: Response(
                    self.response_body(payload)))
            # An ordinary deduplicated replay keeps the same provider IDs.
            submit_handoff(
                **self.case, receipt_db_path=path,
                transport=lambda req, timeout: Response(
                    self.response_body(payload, deduplicated=True)))
            for forged in ({"id": "request-replaced"},
                           {"task_id": "task-replaced"}):
                with self.subTest(forged=forged):
                    with self.assertRaisesRegex(
                            HandoffError, "^provider_receipt_identity_mismatch$"):
                        submit_handoff(
                            **self.case, receipt_db_path=path,
                            transport=lambda req, timeout, forged=forged:
                                Response(self.response_body(payload, **forged)))
            with sqlite3.connect(path) as db:
                rows = db.execute(
                    "SELECT request_id,task_id,deduplicated FROM "
                    "apex_ultra_handoff_receipts").fetchall()
            self.assertEqual(rows, [("request-1", "task-1", 1)])

    def test_backlog_and_network_failures_are_non_secret(self):
        def backlog(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, 429, "full", {}, None)
        with self.assertRaisesRegex(HandoffError, "^provider_backlog_full$"):
            submit_handoff(**self.case, transport=backlog)

        def unavailable(request, timeout):
            raise urllib.error.URLError("private detail")
        with self.assertRaisesRegex(HandoffError, "^provider_unavailable$"):
            submit_handoff(**self.case, transport=unavailable)


if __name__ == "__main__":
    unittest.main()
