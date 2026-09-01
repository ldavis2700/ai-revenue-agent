#!/usr/bin/env python3
"""Idempotently deliver one pre-authorized owned-inbound action."""
import hashlib
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DB_PATH = os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")
ALLOWED_ACTIONS = {"send_initial", "send_followup", "send_checkout", "send_managed_checkout"}
OWNED_INBOUND_SOURCE = "owned_inbound_opt_in"
EVENT_BY_ACTION = {
    "send_initial": "sent",
    "send_followup": "followup_sent",
    "send_checkout": "checkout_sent",
    "send_managed_checkout": "managed_checkout_sent",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def validate(action):
    if action.get("source") != OWNED_INBOUND_SOURCE:
        return False, "source_not_verified_owned_inbound"
    if action.get("action") not in ALLOWED_ACTIONS:
        return False, "action_not_pre_authorized"
    email = str(action.get("email") or "").strip().lower()
    if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
        return False, "valid_delivery_address_required"
    return True, "consented_owned_inbound"


def idempotency_key(action):
    canonical = json.dumps(action, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def connect(path=DB_PATH):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS autonomous_delivery_receipts (
        idempotency_key TEXT PRIMARY KEY, lead_id TEXT, action_type TEXT,
        provider_status TEXT, created_at TEXT
    )""")
    return conn


def deliver(action, path=DB_PATH, transport=None):
    ok, reason = validate(action)
    if not ok:
        return {"status": "blocked", "reason": reason, "lead_id": action.get("lead_id")}
    if os.getenv("DELIVERY_ENABLED", "false").lower() != "true":
        return {"status": "blocked", "reason": "delivery_disabled", "lead_id": action.get("lead_id")}

    endpoint = os.getenv("DELIVERY_WEBHOOK_URL", "").strip()
    token = os.getenv("DELIVERY_WEBHOOK_TOKEN", "").strip()
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc or not token:
        return {"status": "blocked", "reason": "authenticated_https_delivery_required", "lead_id": action.get("lead_id")}

    key = idempotency_key(action)
    conn = connect(path)
    try:
        if conn.execute("SELECT 1 FROM autonomous_delivery_receipts WHERE idempotency_key=?", (key,)).fetchone():
            return {"status": "duplicate", "lead_id": action.get("lead_id"), "idempotency_key": key}
        cap = max(0, int(os.getenv("CONSENTED_INBOUND_DAILY_DELIVERY_CAP", "20")))
        today = datetime.now(timezone.utc).date().isoformat()
        used = conn.execute(
            "SELECT COUNT(*) FROM autonomous_delivery_receipts WHERE provider_status='delivered' AND created_at LIKE ?",
            (today + "%",),
        ).fetchone()[0]
        if used >= cap:
            return {"status": "blocked", "reason": "daily_delivery_cap_reached", "lead_id": action.get("lead_id")}

        body = json.dumps({"action": action, "idempotency_key": key}).encode()
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Idempotency-Key": key,
                "User-Agent": "AI-Revenue-Agent/1.0",
            },
        )
        sender = transport or (lambda req: urllib.request.urlopen(req, timeout=20))
        try:
            response = sender(request)
        except Exception:
            return {"status": "failed", "reason": "delivery_provider_unavailable", "lead_id": action.get("lead_id")}
        status = getattr(response, "status", 200)
        if status < 200 or status >= 300:
            return {"status": "failed", "reason": "delivery_provider_rejected", "lead_id": action.get("lead_id")}
        created_at = now_iso()
        conn.execute(
            "INSERT INTO autonomous_delivery_receipts VALUES (?,?,?,?,?)",
            (key, action.get("lead_id"), action.get("action"), "delivered", created_at),
        )
        event_type = EVENT_BY_ACTION[action.get("action")]
        conn.execute(
            "INSERT INTO events (lead_id,event_type,value,metadata,created_at) VALUES (?,?,?,?,?)",
            (
                action.get("lead_id"),
                event_type,
                0,
                json.dumps({"autonomous": True, "idempotency_key": key, "action": action.get("action")}),
                created_at,
            ),
        )
        conn.commit()
        return {"status": "delivered", "lead_id": action.get("lead_id"), "idempotency_key": key}
    finally:
        conn.close()
