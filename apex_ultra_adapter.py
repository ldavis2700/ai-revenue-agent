#!/usr/bin/env python3
"""Authenticated, idempotent APEX-to-APEX-ULTRA handoff client.

This adapter submits planning requests only. It deliberately rejects any
response that claims execution, production, or outreach authority.
"""
import hashlib
import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


ALLOWED_PROJECTS = {"HAEVEN", "APEX", "RMC_CLASSICS"}
ALLOWED_CAPABILITIES = {"plan", "code_change", "preview_verification"}
ALLOWED_STATUSES = {"queued", "running", "planned", "indeterminate"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
MAX_RESPONSE_BYTES = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 20


class HandoffError(RuntimeError):
    """A safe, non-secret handoff failure."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def make_idempotency_key(*, business_case_id, project, goal,
                         requested_capabilities):
    """Return a stable key for one exact business-case handoff."""
    identity = {
        "origin": "APEX",
        "business_case_id": business_case_id,
        "project": project,
        "goal": goal,
        "requested_capabilities": sorted(set(requested_capabilities)),
    }
    digest = hashlib.sha256(_canonical_json(identity).encode()).hexdigest()
    return "apex:" + digest[:32]


def build_payload(*, business_case_id, project, goal,
                  requested_capabilities, idempotency_key=None):
    capabilities = list(requested_capabilities)
    if project not in ALLOWED_PROJECTS:
        raise HandoffError("project_not_allowlisted")
    if not isinstance(goal, str) or not 8 <= len(goal) <= 5000:
        raise HandoffError("goal_length_invalid")
    if not IDENTIFIER.fullmatch(str(business_case_id)):
        raise HandoffError("business_case_id_invalid")
    if not 1 <= len(capabilities) <= 3:
        raise HandoffError("requested_capability_count_invalid")
    if len(capabilities) != len(set(capabilities)):
        raise HandoffError("requested_capabilities_duplicate")
    if not set(capabilities).issubset(ALLOWED_CAPABILITIES):
        raise HandoffError("requested_capability_not_allowlisted")
    capabilities = sorted(capabilities)
    if idempotency_key is None:
        idempotency_key = make_idempotency_key(
            business_case_id=business_case_id, project=project, goal=goal,
            requested_capabilities=capabilities)
    if not IDENTIFIER.fullmatch(str(idempotency_key)):
        raise HandoffError("idempotency_key_invalid")
    return {
        "origin": "APEX",
        "business_case_id": business_case_id,
        "project": project,
        "goal": goal,
        "requested_capabilities": capabilities,
        "idempotency_key": idempotency_key,
    }


def _endpoint_from_environment():
    if os.getenv("APEX_ULTRA_HANDOFF_ENABLED", "false").lower() != "true":
        raise HandoffError("handoff_disabled")
    base_url = os.getenv("APEX_ULTRA_URL", "").strip()
    allowed_host = os.getenv("APEX_ULTRA_ALLOWED_HOST", "").strip().lower()
    token = os.getenv("APEX_ULTRA_API_TOKEN", "").strip()
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/")):
        raise HandoffError("authenticated_https_endpoint_required")
    if not allowed_host or parsed.hostname.lower() != allowed_host:
        raise HandoffError("endpoint_host_not_allowlisted")
    if len(token) < 16:
        raise HandoffError("api_token_required")
    return base_url.rstrip("/") + "/orchestration/requests", token


def _verified_response(body, payload):
    if not isinstance(body, dict):
        raise HandoffError("provider_response_invalid")
    required_matches = {
        "origin": payload["origin"],
        "business_case_id": payload["business_case_id"],
        "project": payload["project"],
        "goal": payload["goal"],
        "requested_capabilities": payload["requested_capabilities"],
    }
    for field, expected in required_matches.items():
        if body.get(field) != expected:
            raise HandoffError("provider_response_identity_mismatch")
    if body.get("status") not in ALLOWED_STATUSES:
        raise HandoffError("provider_response_status_invalid")
    if not isinstance(body.get("id"), str) or not body["id"]:
        raise HandoffError("provider_request_id_missing")
    if not isinstance(body.get("task_id"), str) or not body["task_id"]:
        raise HandoffError("provider_task_id_missing")
    for field in ("execution_authorized", "production_authorized",
                  "outreach_authorized"):
        if body.get(field) is not False:
            raise HandoffError("provider_response_authority_unsafe")
    if not isinstance(body.get("deduplicated"), bool):
        raise HandoffError("provider_response_deduplication_invalid")
    return body


def _read_json_response(response):
    status = getattr(response, "status", 0)
    if status != 202:
        raise HandoffError("provider_rejected_handoff")
    content_type = str(getattr(response, "headers", {}).get(
        "Content-Type", "")).lower()
    if "application/json" not in content_type:
        raise HandoffError("provider_response_content_type_invalid")
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise HandoffError("provider_response_too_large")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError("provider_response_invalid") from exc


def _record_receipt(path, payload, response):
    if not path:
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload_digest = hashlib.sha256(
        _canonical_json(payload).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS apex_ultra_handoff_receipts (
            idempotency_key TEXT PRIMARY KEY,
            payload_sha256 TEXT NOT NULL,
            request_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            business_case_id TEXT NOT NULL,
            project TEXT NOT NULL,
            status TEXT NOT NULL,
            deduplicated INTEGER NOT NULL,
            recorded_at TEXT NOT NULL
        )""")
        earlier = db.execute(
            "SELECT payload_sha256,request_id,task_id "
            "FROM apex_ultra_handoff_receipts "
            "WHERE idempotency_key=?", (payload["idempotency_key"],)
        ).fetchone()
        if earlier and earlier[0] != payload_digest:
            raise HandoffError("local_idempotency_identity_mismatch")
        if earlier and (earlier[1] != response["id"] or
                        earlier[2] != response["task_id"]):
            raise HandoffError("provider_receipt_identity_mismatch")
        db.execute("""INSERT INTO apex_ultra_handoff_receipts
            (idempotency_key,payload_sha256,request_id,task_id,
             business_case_id,project,status,deduplicated,recorded_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(idempotency_key) DO UPDATE SET
              request_id=excluded.request_id,
              task_id=excluded.task_id,
              status=excluded.status,
              deduplicated=excluded.deduplicated,
              recorded_at=excluded.recorded_at""",
            (payload["idempotency_key"], payload_digest, response["id"],
             response["task_id"], payload["business_case_id"],
             payload["project"], response["status"],
             int(response["deduplicated"]),
             datetime.now(timezone.utc).isoformat()))


def submit_handoff(*, business_case_id, project, goal,
                   requested_capabilities, idempotency_key=None,
                   receipt_db_path=None, transport=None):
    """Submit one bounded handoff and persist its verified provider IDs."""
    payload = build_payload(
        business_case_id=business_case_id, project=project, goal=goal,
        requested_capabilities=requested_capabilities,
        idempotency_key=idempotency_key)
    endpoint, token = _endpoint_from_environment()
    request = urllib.request.Request(
        endpoint, data=_canonical_json(payload).encode(), method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": payload["idempotency_key"],
            "User-Agent": "APEX-Orchestration/1.0",
        })
    sender = transport
    if sender is None:
        opener = urllib.request.build_opener(NoRedirectHandler())
        sender = lambda req, timeout: opener.open(req, timeout=timeout)
    try:
        response = sender(request, DEFAULT_TIMEOUT_SECONDS)
        body = _read_json_response(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise HandoffError("provider_backlog_full") from exc
        if exc.code == 409:
            raise HandoffError("provider_idempotency_conflict") from exc
        raise HandoffError("provider_rejected_handoff") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HandoffError("provider_unavailable") from exc
    finally:
        if "response" in locals() and hasattr(response, "close"):
            response.close()
    verified = _verified_response(body, payload)
    _record_receipt(receipt_db_path, payload, verified)
    return verified
