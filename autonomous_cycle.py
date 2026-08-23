#!/usr/bin/env python3
"""Route AI Revenue Agent work into autonomous, review, and blocked queues.

Only affirmative, owned inbound requests may enter the autonomous dispatch
queue. The module never sends a message itself; an authenticated delivery
adapter consumes that queue and records delivery events idempotently.
"""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

from delivery_adapter import deliver

DB_PATH = os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")
AUTONOMY_ENABLED = os.getenv("CONSENTED_INBOUND_AUTOMATION_ENABLED", "true").lower() == "true"
KILL_SWITCH = os.getenv("REVENUE_AGENT_KILL_SWITCH", "false").lower() == "true"
MAX_DISPATCH = max(0, int(os.getenv("CONSENTED_INBOUND_PER_RUN_CAP", "5")))
OWNED_INBOUND_SOURCE = "owned_inbound_opt_in"
AUTONOMOUS_ACTIONS = {"send_initial", "send_followup", "send_checkout", "send_managed_checkout"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_actions(path=DB_PATH):
    env = {**os.environ, "REVENUE_DB_PATH": path}
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "scripts", "next_actions.py")],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(result.stdout).get("actions", [])


def lead_sources(path=DB_PATH):
    conn = sqlite3.connect(path)
    try:
        return {row[0]: row[1] for row in conn.execute("SELECT id, source FROM leads")}
    finally:
        conn.close()


def route(actions, sources, enabled=AUTONOMY_ENABLED, kill_switch=KILL_SWITCH, cap=MAX_DISPATCH):
    autonomous, review, blocked = [], [], []
    for action in actions:
        enriched = {**action, "source": sources.get(action.get("lead_id"), "unknown")}
        kind = enriched.get("action")
        if kill_switch or not enabled:
            blocked.append({**enriched, "blocked_reason": "autonomy_disabled"})
        elif enriched["source"] != OWNED_INBOUND_SOURCE:
            review.append({**enriched, "review_reason": "source_not_verified_owned_inbound"})
        elif kind not in AUTONOMOUS_ACTIONS:
            review.append({**enriched, "review_reason": "action_not_pre_authorized"})
        elif not enriched.get("email"):
            blocked.append({**enriched, "blocked_reason": "delivery_address_missing"})
        elif len(autonomous) >= cap:
            blocked.append({**enriched, "blocked_reason": "per_run_dispatch_cap_reached"})
        else:
            autonomous.append(enriched)
    return autonomous, review, blocked


def run(path=DB_PATH):
    actions = load_actions(path)
    autonomous, review, blocked = route(actions, lead_sources(path))
    delivery_results = [deliver(action, path) for action in autonomous]
    return {
        "generated_at": now_iso(),
        "mode": "consented_inbound_autonomy" if AUTONOMY_ENABLED and not KILL_SWITCH else "paused",
        "autonomous_dispatch": autonomous,
        "owner_review": review,
        "blocked": blocked,
        "delivery_results": delivery_results,
        "counts": {
            "autonomous_dispatch": len(autonomous),
            "owner_review": len(review),
            "blocked": len(blocked),
            "delivered": sum(1 for result in delivery_results if result["status"] == "delivered"),
        },
        "guardrails": {
            "owned_inbound_only": True,
            "spending_allowed": False,
            "contracts_allowed": False,
            "automatic_charging_allowed": False,
            "unsolicited_outreach_allowed": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run()))
