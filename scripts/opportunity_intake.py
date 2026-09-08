#!/usr/bin/env python3
"""Normalize, screen, deduplicate, and rank paid-work opportunities.

This module is deliberately an intake boundary, not an application bot.  It may
recommend autonomous submission only when the source explicitly says that
automation is permitted, the authenticated channel is available, and the
opportunity itself carries an affirmative submission authorization.
"""
import argparse
import hashlib
import json
import math
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit


DEFAULT_MAX_AGE_DAYS = 30
DEFAULT_DB_PATH = "/files/data/revenue_agent.db"
MAX_FUTURE_SKEW = timedelta(minutes=5)
PROHIBITED_CATEGORIES = {
    "adult", "credential_theft", "deceptive_reviews", "fraud", "malware",
    "regulated_financial_advice", "spam", "surveillance",
}
PIPELINE_TRANSITIONS = {
    "payment_rail_blocked": {"qualified"},
    "qualified": {"proposal_ready", "unqualified", "expired"},
    "proposal_ready": {"submitted", "unqualified", "expired"},
    "submitted": {"response_received", "unqualified", "expired"},
    "response_received": {"contracted", "unqualified"},
    "contracted": {"executing"},
    "executing": {"qa_passed"},
    "qa_passed": {"delivered"},
    "delivered": {"invoiced"},
    "invoiced": {"collected"},
}
PIPELINE_EVIDENCE_PREFIXES = {
    "qualified": ("payment_rail:",),
    "proposal_ready": ("proposal:",),
    "submitted": ("submission:",),
    "response_received": ("reply:",),
    "contracted": ("contract:",),
    "executing": ("contract:",),
    "qa_passed": ("qa:",),
    "delivered": ("delivery:",),
    "invoiced": ("invoice:",),
    "collected": ("verified_payment:",),
    "unqualified": ("screen:",),
    "expired": ("expiry:",),
}


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}_timezone_required")
    return parsed.astimezone(timezone.utc)


def finite_number(payload, field, *, minimum=0, maximum=None, required=True):
    value = payload.get(field)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field}_invalid")
    value = float(value)
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{field}_invalid")
    return value


def canonical_url(value):
    if not value:
        return ""
    try:
        parsed = urlsplit(str(value).strip())
    except ValueError as exc:
        raise ValueError("url_invalid") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url_invalid")
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = f":{parsed.port}" if parsed.port else ""
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), host + port, path, parsed.query, ""))


def stable_id(source, external_id, url):
    # A provider's immutable external ID wins over a mutable/listing URL.
    identity = f"{source.lower()}|{external_id.lower() or url.lower()}"
    return "opp_" + hashlib.sha256(identity.encode()).hexdigest()[:20]


def payload_hash(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        encoded = repr(value)
    return hashlib.sha256(encoded.encode()).hexdigest()


def normalize(payload, *, now=None, max_age_days=DEFAULT_MAX_AGE_DAYS):
    if not isinstance(payload, dict):
        raise ValueError("opportunity_object_required")
    now = now or utc_now()
    title = str(payload.get("title") or "").strip()
    source = str(payload.get("source") or "").strip()
    external_id = str(payload.get("external_id") or "").strip()
    url = canonical_url(payload.get("url"))
    if not title:
        raise ValueError("title_required")
    if not source:
        raise ValueError("source_required")
    if not external_id and not url:
        raise ValueError("external_id_or_url_required")

    observed = parse_time(payload.get("observed_at"), "observed_at")
    if observed > now + MAX_FUTURE_SKEW:
        raise ValueError("observed_at_future")
    if observed < now - timedelta(days=max_age_days):
        raise ValueError("opportunity_stale")
    expires = None
    if payload.get("expires_at") is not None:
        expires = parse_time(payload.get("expires_at"), "expires_at")
        if expires <= now:
            raise ValueError("opportunity_expired")

    payout_cents = finite_number(payload, "payout_cents", minimum=0)
    effort_hours = finite_number(payload, "effort_hours", minimum=0.25, maximum=10000)
    time_to_cash_days = finite_number(payload, "time_to_cash_days", minimum=0, maximum=3650)
    normalized = {
        "id": stable_id(source, external_id, url),
        "source": source,
        "external_id": external_id,
        "url": url,
        "title": title,
        "description": str(payload.get("description") or "").strip(),
        "observed_at": observed.isoformat(),
        "expires_at": expires.isoformat() if expires else None,
        "payout_cents": int(payout_cents),
        "currency": str(payload.get("currency") or "USD").strip().upper(),
        "effort_hours": effort_hours,
        "time_to_cash_days": time_to_cash_days,
        "buyer_intent": finite_number(payload, "buyer_intent", maximum=1),
        "win_probability": finite_number(payload, "win_probability", maximum=1),
        "execution_confidence": finite_number(payload, "execution_confidence", maximum=1),
        "payment_risk": finite_number(payload, "payment_risk", maximum=1),
        "reuse_value": finite_number(payload, "reuse_value", maximum=1),
        "recurring_value": finite_number(payload, "recurring_value", maximum=1),
        "prohibited_category": str(payload.get("prohibited_category") or "").strip().lower(),
        "scam_signals": [str(x).strip() for x in (payload.get("scam_signals") or []) if str(x).strip()],
        "requires_deception": bool(payload.get("requires_deception", False)),
        "requires_owner_identity": bool(payload.get("requires_owner_identity", False)),
        "unsolicited_direct_contact": bool(payload.get("unsolicited_direct_contact", False)),
        "suppressed": bool(payload.get("suppressed", False)),
        "opted_out": bool(payload.get("opted_out", False)),
        "payment_rail_status": str(payload.get("payment_rail_status") or
                                   ("clear" if payload.get("payment_rail_clear", False) else "unclear")).strip().lower(),
        "platform_allows_automation": bool(payload.get("platform_allows_automation", False)),
        "authenticated_channel": bool(payload.get("authenticated_channel", False)),
        "submission_authorized": bool(payload.get("submission_authorized", False)),
    }
    if not re.fullmatch(r"[A-Z]{3}", normalized["currency"]):
        raise ValueError("currency_invalid")
    if normalized["payment_rail_status"] not in {"clear", "temporarily_unavailable", "unclear"}:
        raise ValueError("payment_rail_status_invalid")
    return normalized


def screen(opportunity):
    if opportunity["prohibited_category"] in PROHIBITED_CATEGORIES:
        return False, "prohibited_category"
    if opportunity["scam_signals"]:
        return False, "scam_signals_present"
    if opportunity["requires_deception"]:
        return False, "deception_required"
    if opportunity["unsolicited_direct_contact"]:
        return False, "unsolicited_contact_disallowed"
    if opportunity["suppressed"] or opportunity["opted_out"]:
        return False, "suppressed_or_opted_out"
    if opportunity["payment_rail_status"] == "unclear":
        return False, "payment_rail_unclear"
    if opportunity["execution_confidence"] < 0.6:
        return False, "execution_confidence_too_low"
    return True, "eligible"


def score(opportunity):
    """Return a bounded 0-100 expected-value score with explicit components."""
    expected_value = opportunity["payout_cents"] * opportunity["win_probability"]
    dollars_per_hour = expected_value / 100 / opportunity["effort_hours"]
    value_score = min(dollars_per_hour / 100, 1)
    speed_score = max(0, 1 - opportunity["time_to_cash_days"] / 60)
    components = {
        "buyer_intent": 15 * opportunity["buyer_intent"],
        "expected_value": 15 * value_score,
        "win_probability": 15 * opportunity["win_probability"],
        "execution_confidence": 20 * opportunity["execution_confidence"],
        "time_to_cash": 15 * speed_score,
        "payment_safety": 10 * (1 - opportunity["payment_risk"]),
        "reuse_and_recurring": 5 * opportunity["reuse_value"] + 5 * opportunity["recurring_value"],
    }
    return round(sum(components.values()), 2), {key: round(value, 2) for key, value in components.items()}


def action_mode(opportunity):
    if (opportunity["platform_allows_automation"] and opportunity["authenticated_channel"]
            and opportunity["submission_authorized"] and not opportunity["requires_owner_identity"]
            and opportunity["payment_rail_status"] == "clear"):
        return "autonomous_submit"
    return "prepare_only"


def ingest(payloads, *, now=None, max_age_days=DEFAULT_MAX_AGE_DAYS):
    now = now or utc_now()
    accepted, rejected, by_id = [], [], {}
    for index, payload in enumerate(payloads):
        try:
            item = normalize(payload, now=now, max_age_days=max_age_days)
            eligible, reason = screen(item)
            if not eligible:
                rejected.append({"index": index, "reason": reason, "id": item["id"],
                                 "payload_hash": payload_hash(payload)})
                continue
            previous = by_id.get(item["id"])
            if previous and previous["observed_at"] >= item["observed_at"]:
                rejected.append({"index": index, "reason": "duplicate_older_or_equal", "id": item["id"],
                                 "payload_hash": payload_hash(payload)})
                continue
            if previous:
                accepted.remove(previous)
                rejected.append({"index": previous["_index"], "reason": "duplicate_superseded", "id": item["id"],
                                 "payload_hash": previous["_payload_hash"]})
            item["score"], item["score_components"] = score(item)
            item["action_mode"] = action_mode(item)
            item["pipeline_state"] = ("payment_rail_blocked"
                                      if item["payment_rail_status"] == "temporarily_unavailable"
                                      else "qualified")
            item["source_index"] = index
            item["_index"] = index
            item["_payload_hash"] = payload_hash(payload)
            by_id[item["id"]] = item
            accepted.append(item)
        except ValueError as exc:
            rejected.append({"index": index, "reason": str(exc)})
    accepted.sort(key=lambda item: (-item["score"], item["time_to_cash_days"], item["id"]))
    for item in accepted:
        item.pop("_index", None)
        item.pop("_payload_hash", None)
    for rejection in rejected:
        rejection.setdefault("payload_hash", payload_hash(payloads[rejection["index"]]))
    return {"metrics": {"received": len(payloads), "eligible": len(accepted), "rejected": len(rejected)},
            "opportunities": accepted, "rejections": rejected}


def open_ledger(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("""CREATE TABLE IF NOT EXISTS opportunities (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        score REAL NOT NULL,
        action_mode TEXT NOT NULL,
        pipeline_state TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS opportunity_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT,
        decision TEXT NOT NULL,
        reason TEXT NOT NULL,
        source_index INTEGER NOT NULL,
        payload_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS opportunity_transitions (
        transition_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        from_state TEXT NOT NULL,
        to_state TEXT NOT NULL,
        evidence_id TEXT NOT NULL,
        evidence_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS proposal_artifacts (
        proposal_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        artifact_hash TEXT NOT NULL,
        artifact_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        UNIQUE(opportunity_id, artifact_hash)
    )""")
    return connection


def receipt_id(opportunity_id, decision, reason, source_index, digest):
    value = f"{opportunity_id or ''}|{decision}|{reason}|{source_index}|{digest}"
    return "oppr_" + hashlib.sha256(value.encode()).hexdigest()[:24]


def transition_id(opportunity_id, from_state, to_state, evidence_id):
    value = f"{opportunity_id}|{from_state}|{to_state}|{evidence_id}"
    return "oppt_" + hashlib.sha256(value.encode()).hexdigest()[:24]


def _proposal_text(value, field, maximum):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{field}_too_long")
    return value


def prepare_proposal(path, opportunity_id, proposal, *, now=None):
    """Persist a truthful proposal and advance qualified work atomically.

    Claims are optional, but every included claim needs an HTTPS evidence source
    and an explicit verification timestamp. This prepares a proposal only; it
    never submits, contacts, contracts, invoices, or charges.
    """
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(proposal, dict):
        raise ValueError("proposal_object_required")
    opportunity_id = opportunity_id.strip()
    scope = _proposal_text(proposal.get("scope"), "scope", 2000)
    price_cents = finite_number(proposal, "price_cents", minimum=1)
    if not price_cents.is_integer():
        raise ValueError("price_cents_invalid")
    milestones = proposal.get("milestones")
    if not isinstance(milestones, list) or not 1 <= len(milestones) <= 8:
        raise ValueError("milestones_invalid")
    normalized_milestones = []
    milestone_total = 0
    for milestone in milestones:
        if not isinstance(milestone, dict):
            raise ValueError("milestone_invalid")
        title = _proposal_text(milestone.get("title"), "milestone_title", 160)
        deliverable = _proposal_text(milestone.get("deliverable"), "milestone_deliverable", 1000)
        amount = finite_number(milestone, "amount_cents", minimum=1)
        days = finite_number(milestone, "due_days", minimum=1, maximum=365)
        if not amount.is_integer() or not days.is_integer():
            raise ValueError("milestone_number_invalid")
        milestone_total += int(amount)
        normalized_milestones.append({"title": title, "deliverable": deliverable,
                                      "amount_cents": int(amount), "due_days": int(days)})
    if milestone_total != int(price_cents):
        raise ValueError("milestone_total_mismatch")

    claims = proposal.get("claims", [])
    if not isinstance(claims, list) or len(claims) > 20:
        raise ValueError("claims_invalid")
    normalized_claims = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("claim_invalid")
        text = _proposal_text(claim.get("text"), "claim_text", 500)
        source_url = canonical_url(
            _proposal_text(claim.get("source_url"), "claim_source_url", 2000))
        if urlsplit(source_url).scheme != "https":
            raise ValueError("claim_source_url_https_required")
        verified_at = parse_time(claim.get("verified_at"), "claim_verified_at")
        recorded_at = now or utc_now()
        if verified_at > recorded_at + MAX_FUTURE_SKEW:
            raise ValueError("claim_verified_at_future")
        normalized_claims.append({"text": text, "source_url": source_url,
                                  "verified_at": verified_at.isoformat()})

    artifact = {"opportunity_id": opportunity_id, "scope": scope,
                "price_cents": int(price_cents), "milestones": normalized_milestones,
                "claims": normalized_claims}
    serialized = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    artifact_hash = hashlib.sha256(serialized.encode()).hexdigest()
    proposal_id = "prop_" + artifact_hash[:24]
    evidence_id = "proposal:" + proposal_id
    created_at = (now or utc_now()).isoformat()
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            existing = connection.execute(
                "SELECT 1 FROM proposal_artifacts WHERE proposal_id=?", (proposal_id,)).fetchone()
            if row[0] == "proposal_ready" and existing:
                return {"proposal_id": proposal_id, "changed": False, "state": row[0]}
            if row[0] != "qualified":
                raise ValueError("pipeline_state_conflict")
            opportunity = json.loads(row[1])
            if artifact["price_cents"] > opportunity["payout_cents"]:
                raise ValueError("price_exceeds_opportunity_payout")
            tid = transition_id(opportunity_id, "qualified", "proposal_ready", evidence_id)
            connection.execute("""INSERT INTO proposal_artifacts
                (proposal_id,opportunity_id,artifact_hash,artifact_json,created_at)
                VALUES (?,?,?,?,?)""", (
                    proposal_id, opportunity_id, artifact_hash, serialized, created_at))
            opportunity["pipeline_state"] = "proposal_ready"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("proposal_ready", json.dumps(opportunity, sort_keys=True, separators=(",", ":")),
                 created_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "qualified", "proposal_ready", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), created_at))
        return {"proposal_id": proposal_id, "changed": True, "state": "proposal_ready"}
    finally:
        connection.close()


def record_transition(path, opportunity_id, expected_state, to_state, evidence_id, *, now=None):
    """Record one evidence-backed, no-skip pipeline transition atomically.

    This changes ledger state only. It never submits, contacts, contracts, delivers,
    invoices, or charges through an external provider.
    """
    values = (opportunity_id, expected_state, to_state, evidence_id)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("transition_fields_required")
    opportunity_id, expected_state, to_state, evidence_id = (value.strip() for value in values)
    if to_state not in PIPELINE_TRANSITIONS.get(expected_state, set()):
        raise ValueError("transition_not_allowed")
    if not evidence_id.startswith(PIPELINE_EVIDENCE_PREFIXES[to_state]):
        raise ValueError("transition_evidence_invalid")
    recorded_at = (now or utc_now()).isoformat()
    evidence_hash = hashlib.sha256(evidence_id.encode()).hexdigest()
    tid = transition_id(opportunity_id, expected_state, to_state, evidence_id)
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state, payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            if row[0] == to_state:
                existing = connection.execute(
                    "SELECT 1 FROM opportunity_transitions WHERE transition_id=?", (tid,)).fetchone()
                if existing:
                    return {"transition_id": tid, "changed": False, "state": to_state}
            if row[0] != expected_state:
                raise ValueError("pipeline_state_conflict")
            payload = json.loads(row[1])
            payload["pipeline_state"] = to_state
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?, payload_json=?, updated_at=? WHERE id=?",
                (to_state, json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, expected_state, to_state, evidence_id,
                    evidence_hash, recorded_at))
        return {"transition_id": tid, "changed": True, "state": to_state}
    finally:
        connection.close()


def persist(result, path=DEFAULT_DB_PATH, *, now=None):
    """Atomically persist eligible opportunities and idempotent decision receipts."""
    now = (now or utc_now()).isoformat()
    connection = open_ledger(path)
    written, unchanged, receipt_writes = 0, 0, 0
    try:
        with connection:
            for index, item in enumerate(result["opportunities"]):
                serialized = json.dumps(item, sort_keys=True, separators=(",", ":"))
                cursor = connection.execute("""INSERT INTO opportunities
                    (id,source,external_id,url,title,score,action_mode,pipeline_state,
                     observed_at,payload_json,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                      source=excluded.source, external_id=excluded.external_id,
                      url=excluded.url, title=excluded.title, score=excluded.score,
                      action_mode=excluded.action_mode, pipeline_state=excluded.pipeline_state,
                      observed_at=excluded.observed_at, payload_json=excluded.payload_json,
                      updated_at=excluded.updated_at
                    WHERE excluded.observed_at > opportunities.observed_at""", (
                        item["id"], item["source"], item["external_id"], item["url"],
                        item["title"], item["score"], item["action_mode"], item["pipeline_state"],
                        item["observed_at"], serialized, now))
                if cursor.rowcount:
                    written += 1
                else:
                    unchanged += 1
                digest = payload_hash(item)
                source_index = item.get("source_index", index)
                rid = receipt_id(item["id"], "eligible", item["action_mode"], source_index, digest)
                receipt_writes += connection.execute("""INSERT OR IGNORE INTO opportunity_receipts
                    (receipt_id,opportunity_id,decision,reason,source_index,payload_hash,recorded_at)
                    VALUES (?,?,?,?,?,?,?)""", (
                        rid, item["id"], "eligible", item["action_mode"], source_index, digest, now)).rowcount
            for rejected in result["rejections"]:
                rid = receipt_id(rejected.get("id"), "rejected", rejected["reason"],
                                 rejected["index"], rejected["payload_hash"])
                receipt_writes += connection.execute("""INSERT OR IGNORE INTO opportunity_receipts
                    (receipt_id,opportunity_id,decision,reason,source_index,payload_hash,recorded_at)
                    VALUES (?,?,?,?,?,?,?)""", (
                        rid, rejected.get("id"), "rejected", rejected["reason"],
                        rejected["index"], rejected["payload_hash"], now)).rowcount
        return {"opportunities_written": written, "opportunities_unchanged": unchanged,
                "receipts_written": receipt_writes}
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="Screen and rank paid-work opportunities")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--database", help="persist decisions to the opportunity ledger")
    args = parser.parse_args()
    if args.max_age_days < 1:
        raise SystemExit("max-age-days must be positive")
    raw = sys.stdin.read().strip()
    data = json.loads(raw or "[]")
    payloads = data if isinstance(data, list) else data.get("opportunities", [])
    if not isinstance(payloads, list):
        raise SystemExit("opportunities must be a list")
    result = ingest(payloads, max_age_days=args.max_age_days)
    if args.database:
        result["persistence"] = persist(result, args.database)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
