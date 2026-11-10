"""Isolate delivery faults without replaying actions with uncertain outcomes.

The journal is committed before external delivery. Pending attempts survive
process death and require a matching committed adapter receipt or reconciliation.
This is not a scheduler and never enables delivery or overrides a stop control.
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from delivery_adapter import idempotency_key


def _connect(path):
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS autonomous_dispatch_pending (
            work_key TEXT PRIMARY KEY,
            attempt_id TEXT NOT NULL,
            payload_key TEXT NOT NULL,
            started_at TEXT NOT NULL
        )""")
        conn.commit()
    except BaseException:
        conn.close()
        raise
    return conn


def _receipt_exists(conn, payload_key):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='autonomous_delivery_receipts'"
    ).fetchone()
    return bool(exists and conn.execute(
        "SELECT 1 FROM autonomous_delivery_receipts "
        "WHERE idempotency_key=? AND provider_status='delivered'",
        (payload_key,),
    ).fetchone())


def _release(conn, work_key, attempt_id):
    conn.execute(
        "DELETE FROM autonomous_dispatch_pending WHERE work_key=? AND attempt_id=?",
        (work_key, attempt_id),
    )
    conn.commit()


def dispatch_one(action, path, deliver):
    identity = {"lead_id": action.get("lead_id"), "action": action.get("action")}
    # A changed payload must not bypass an uncertain attempt for the same work.
    work_key = idempotency_key(identity)
    payload_key = idempotency_key(action)
    attempt_id = str(uuid.uuid4())
    conn = _connect(path)
    try:
        claimed = conn.execute(
            "INSERT OR IGNORE INTO autonomous_dispatch_pending VALUES (?,?,?,?)",
            (work_key, attempt_id, payload_key, datetime.now(timezone.utc).isoformat()),
        ).rowcount == 1
        conn.commit()
        if not claimed:
            pending_id, pending_payload = conn.execute(
                "SELECT attempt_id,payload_key FROM autonomous_dispatch_pending WHERE work_key=?",
                (work_key,),
            ).fetchone()
            if pending_payload == payload_key and _receipt_exists(conn, payload_key):
                _release(conn, work_key, pending_id)
                return {"status": "duplicate", "reason": "committed_receipt_recovered",
                        **identity, "idempotency_key": payload_key}
            return {"status": "uncertain", "reason": "prior_attempt_requires_reconciliation",
                    **identity}

        # Do not swallow KeyboardInterrupt/SystemExit: the pending row survives
        # and protects the next process from replay after an intentional stop.
        try:
            result = deliver(action, path)
        except Exception:
            return {"status": "uncertain", "reason": "delivery_outcome_requires_reconciliation",
                    **identity}
        if not isinstance(result, dict) or result.get("status") not in {
            "delivered", "duplicate", "blocked", "failed"
        }:
            return {"status": "uncertain", "reason": "invalid_delivery_result",
                    **identity}
        if result["status"] == "failed":
            # A provider failure/timeout can occur after it accepted the work.
            # Do not automatically resend even if the next cycle is healthy.
            return {"status": "uncertain", "reason": "delivery_outcome_requires_reconciliation",
                    **identity}
        if result["status"] in {"delivered", "duplicate"} and not _receipt_exists(conn, payload_key):
            return {"status": "uncertain", "reason": "delivery_receipt_not_committed",
                    **identity}
        _release(conn, work_key, attempt_id)
        return result
    finally:
        conn.close()


def dispatch_actions(actions, path, deliver):
    results = []
    for action in actions:
        if (os.getenv("REVENUE_AGENT_KILL_SWITCH", "false").lower() == "true"
                or os.getenv("CONSENTED_INBOUND_AUTOMATION_ENABLED", "true").lower() != "true"):
            results.append({"status": "blocked", "reason": "autonomy_disabled",
                            "lead_id": action.get("lead_id")})
            continue
        try:
            results.append(dispatch_one(action, path, deliver))
        except Exception:
            # Database/journal faults fail closed. No exception text, payload,
            # email, token or provider URL is copied into the diagnostic.
            results.append({"status": "uncertain", "reason": "dispatch_journal_unavailable",
                            "lead_id": action.get("lead_id")})
    return results
