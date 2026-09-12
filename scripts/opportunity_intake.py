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
MAX_APPLICATION_BALANCE_AGE = timedelta(minutes=15)
MAX_SUBMISSION_AUTHORIZATION_AGE = timedelta(minutes=30)
MAX_APPLICATION_SPEND_AUTHORIZATION_AGE = timedelta(minutes=30)
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


def boolean_flag(payload, field, *, default=False):
    """Accept only explicit JSON booleans for policy-sensitive evidence."""
    value = payload.get(field, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field}_invalid")
    return value


def capability_set(payload, field):
    """Normalize explicit execution capabilities without guessing from free text."""
    values = payload.get(field, [])
    if not isinstance(values, list):
        raise ValueError(f"{field}_invalid")
    normalized = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field}_invalid")
        capability = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", capability):
            raise ValueError(f"{field}_invalid")
        normalized.add(capability)
    return sorted(normalized)


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
    opportunity_id = stable_id(source, external_id, url)

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

    payout_cents = finite_number(payload, "payout_cents", minimum=1)
    if not payout_cents.is_integer():
        raise ValueError("payout_cents_invalid")
    effort_hours = finite_number(payload, "effort_hours", minimum=0.25, maximum=10000)
    time_to_cash_days = finite_number(payload, "time_to_cash_days", minimum=0, maximum=3650)
    required_capabilities = capability_set(payload, "required_execution_capabilities")
    available_capabilities = capability_set(payload, "available_execution_capabilities")
    application_cost_units = finite_number(
        payload, "application_cost_units", minimum=0, maximum=10000, required=False)
    application_units_balance = finite_number(
        payload, "application_units_balance", minimum=0, maximum=1000000, required=False)
    positions_to_hire = finite_number(
        payload, "positions_to_hire", minimum=1, maximum=10000, required=False)
    hires_for_listing = finite_number(
        payload, "hires_for_listing", minimum=0, maximum=10000, required=False)
    if application_cost_units is not None and not application_cost_units.is_integer():
        raise ValueError("application_cost_units_invalid")
    if application_units_balance is not None and not application_units_balance.is_integer():
        raise ValueError("application_units_balance_invalid")
    if positions_to_hire is not None and not positions_to_hire.is_integer():
        raise ValueError("positions_to_hire_invalid")
    if hires_for_listing is not None and not hires_for_listing.is_integer():
        raise ValueError("hires_for_listing_invalid")
    application_balance_observed = None
    if payload.get("application_balance_observed_at") is not None:
        application_balance_observed = parse_time(
            payload.get("application_balance_observed_at"),
            "application_balance_observed_at")
        if application_balance_observed > now + MAX_FUTURE_SKEW:
            raise ValueError("application_balance_observed_at_future")
    if application_cost_units and application_units_balance is not None:
        if application_balance_observed is None:
            raise ValueError("application_balance_observed_at_required")
        if application_balance_observed < now - MAX_APPLICATION_BALANCE_AGE:
            raise ValueError("application_balance_stale")
    payment_rail_clear = boolean_flag(payload, "payment_rail_clear")
    payment_rail_status = str(
        payload.get("payment_rail_status") or
        ("clear" if payment_rail_clear else "unclear")
    ).strip().lower()
    if payment_rail_status not in {"clear", "temporarily_unavailable", "unclear"}:
        raise ValueError("payment_rail_status_invalid")
    if payment_rail_clear != (payment_rail_status == "clear"):
        raise ValueError("payment_rail_evidence_conflict")
    platform_allows_automation = boolean_flag(payload, "platform_allows_automation")
    authenticated_channel = boolean_flag(payload, "authenticated_channel")
    submission_authorized = boolean_flag(payload, "submission_authorized")
    submission_authorization_id = payload.get(
        "submission_authorization_opportunity_id")
    submission_authorized_at = None
    if submission_authorized:
        if (not isinstance(submission_authorization_id, str)
                or not submission_authorization_id.strip()):
            raise ValueError("submission_authorization_opportunity_id_required")
        submission_authorization_id = submission_authorization_id.strip()
        if submission_authorization_id != opportunity_id:
            raise ValueError("submission_authorization_opportunity_mismatch")
        submission_authorized_at = parse_time(
            payload.get("submission_authorized_at"), "submission_authorized_at")
        if submission_authorized_at > now + MAX_FUTURE_SKEW:
            raise ValueError("submission_authorized_at_future")
        if submission_authorized_at < now - MAX_SUBMISSION_AUTHORIZATION_AGE:
            raise ValueError("submission_authorization_stale")
    application_spend_authorized = boolean_flag(
        payload, "application_spend_authorized")
    application_spend_authorization_id = payload.get(
        "application_spend_authorization_opportunity_id")
    application_spend_authorized_units = None
    application_spend_authorized_at = None
    if application_spend_authorized:
        if not application_cost_units:
            raise ValueError("application_spend_authorization_unnecessary")
        if (not isinstance(application_spend_authorization_id, str)
                or not application_spend_authorization_id.strip()):
            raise ValueError(
                "application_spend_authorization_opportunity_id_required")
        application_spend_authorization_id = (
            application_spend_authorization_id.strip())
        if application_spend_authorization_id != opportunity_id:
            raise ValueError("application_spend_authorization_opportunity_mismatch")
        application_spend_authorized_units = finite_number(
            payload, "application_spend_authorized_units", minimum=0,
            maximum=10000)
        if (not application_spend_authorized_units.is_integer()
                or application_spend_authorized_units != application_cost_units):
            raise ValueError("application_spend_authorized_units_mismatch")
        application_spend_authorized_at = parse_time(
            payload.get("application_spend_authorized_at"),
            "application_spend_authorized_at")
        if application_spend_authorized_at > now + MAX_FUTURE_SKEW:
            raise ValueError("application_spend_authorized_at_future")
        if (application_spend_authorized_at
                < now - MAX_APPLICATION_SPEND_AUTHORIZATION_AGE):
            raise ValueError("application_spend_authorization_stale")
    requires_credential_access = boolean_flag(payload, "requires_credential_access")
    credential_access_method = str(
        payload.get("credential_access_method") or
        ("unclear" if requires_credential_access else "none")
    ).strip().lower()
    normalized = {
        "id": opportunity_id,
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
        "requires_deception": boolean_flag(payload, "requires_deception"),
        "requires_owner_identity": boolean_flag(payload, "requires_owner_identity"),
        "unsolicited_direct_contact": boolean_flag(
            payload, "unsolicited_direct_contact"),
        "suppressed": boolean_flag(payload, "suppressed"),
        "opted_out": boolean_flag(payload, "opted_out"),
        "payment_rail_status": payment_rail_status,
        "platform_allows_automation": platform_allows_automation,
        "authenticated_channel": authenticated_channel,
        "submission_authorized": submission_authorized,
        "submission_authorization_opportunity_id": (
            submission_authorization_id if submission_authorized else None),
        "submission_authorized_at": (
            submission_authorized_at.isoformat()
            if submission_authorized_at else None),
        "submission_channel_status": str(
            payload.get("submission_channel_status") or
            ("available" if authenticated_channel else "unclear")
        ).strip().lower(),
        "listing_open": boolean_flag(payload, "listing_open", default=True),
        "positions_to_hire": (int(positions_to_hire)
                              if positions_to_hire is not None else None),
        "hires_for_listing": (int(hires_for_listing)
                              if hires_for_listing is not None else None),
        "preferred_qualifications_met": boolean_flag(
            payload, "preferred_qualifications_met", default=True),
        "application_cost_units": int(application_cost_units or 0),
        "application_units_balance": (int(application_units_balance)
                                      if application_units_balance is not None else None),
        "application_balance_observed_at": (
            application_balance_observed.isoformat()
            if application_balance_observed else None),
        "application_spend_authorized": application_spend_authorized,
        "application_spend_authorization_opportunity_id": (
            application_spend_authorization_id
            if application_spend_authorized else None),
        "application_spend_authorized_units": (
            int(application_spend_authorized_units)
            if application_spend_authorized_units is not None else None),
        "application_spend_authorized_at": (
            application_spend_authorized_at.isoformat()
            if application_spend_authorized_at else None),
        "requires_personal_data_collection": boolean_flag(
            payload, "requires_personal_data_collection"),
        "personal_data_authorized": boolean_flag(payload, "personal_data_authorized"),
        "requires_credential_access": requires_credential_access,
        "credential_access_method": credential_access_method,
        "required_execution_capabilities": required_capabilities,
        "available_execution_capabilities": available_capabilities,
        "missing_execution_capabilities": sorted(
            set(required_capabilities) - set(available_capabilities)),
    }
    if not re.fullmatch(r"[A-Z]{3}", normalized["currency"]):
        raise ValueError("currency_invalid")
    if normalized["submission_channel_status"] not in {
            "available", "temporarily_unavailable", "unclear"}:
        raise ValueError("submission_channel_status_invalid")
    if normalized["credential_access_method"] not in {
            "none", "provider_managed", "tokenized", "raw", "unclear"}:
        raise ValueError("credential_access_method_invalid")
    return normalized


def screen(opportunity):
    if not opportunity["listing_open"]:
        return False, "listing_closed"
    if (opportunity["positions_to_hire"] is not None
            and opportunity["hires_for_listing"] is not None
            and opportunity["hires_for_listing"] >= opportunity["positions_to_hire"]):
        return False, "listing_filled"
    if not opportunity["preferred_qualifications_met"]:
        return False, "preferred_qualifications_unmet"
    if (opportunity["application_cost_units"] > 0
            and opportunity["application_units_balance"] is None):
        return False, "application_balance_unverified"
    if (opportunity["application_units_balance"] is not None
            and opportunity["application_cost_units"]
            > opportunity["application_units_balance"]):
        return False, "insufficient_application_units"
    if opportunity["missing_execution_capabilities"]:
        return False, "execution_capabilities_unmet"
    if (opportunity["requires_personal_data_collection"]
            and not opportunity["personal_data_authorized"]):
        return False, "personal_data_authority_unverified"
    if (opportunity["requires_credential_access"]
            and opportunity["credential_access_method"] not in {
                "provider_managed", "tokenized"}):
        return False, "credential_access_unsafe"
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
        "application_cost": -10 * min(
            opportunity["application_cost_units"] /
            max(opportunity["application_units_balance"] or 1, 1), 1),
    }
    return round(sum(components.values()), 2), {key: round(value, 2) for key, value in components.items()}


def action_mode(opportunity):
    if (opportunity["platform_allows_automation"] and opportunity["authenticated_channel"]
            and opportunity["submission_authorized"] and not opportunity["requires_owner_identity"]
            and (opportunity["application_cost_units"] == 0
                 or opportunity["application_spend_authorized"])
            and opportunity["payment_rail_status"] == "clear"
            and opportunity["submission_channel_status"] == "available"):
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
    connection.execute("""CREATE TABLE IF NOT EXISTS submission_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_submission_id TEXT NOT NULL,
        submission_url TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(proposal_id) REFERENCES proposal_artifacts(proposal_id),
        UNIQUE(provider, external_submission_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS response_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        submission_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_message_id TEXT NOT NULL,
        message_url TEXT NOT NULL,
        received_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(submission_receipt_id) REFERENCES submission_receipts(receipt_id),
        UNIQUE(provider, external_message_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS contract_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        response_receipt_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_contract_id TEXT NOT NULL,
        contract_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        contracted_at TEXT NOT NULL,
        terms_authority TEXT NOT NULL,
        authority_evidence_url TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(response_receipt_id) REFERENCES response_receipts(receipt_id),
        FOREIGN KEY(proposal_id) REFERENCES proposal_artifacts(proposal_id),
        UNIQUE(provider, external_contract_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS execution_plans (
        plan_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        contract_receipt_id TEXT NOT NULL,
        plan_hash TEXT NOT NULL,
        plan_json TEXT NOT NULL,
        started_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(contract_receipt_id) REFERENCES contract_receipts(receipt_id),
        UNIQUE(opportunity_id, plan_hash)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS qa_reports (
        report_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        execution_plan_id TEXT NOT NULL,
        artifact_sha256 TEXT NOT NULL,
        report_hash TEXT NOT NULL,
        report_json TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(execution_plan_id) REFERENCES execution_plans(plan_id),
        UNIQUE(opportunity_id, report_hash)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS delivery_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        qa_report_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_delivery_id TEXT NOT NULL,
        delivery_url TEXT NOT NULL,
        artifact_sha256 TEXT NOT NULL,
        delivered_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(qa_report_id) REFERENCES qa_reports(report_id),
        UNIQUE(provider, external_delivery_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS invoice_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        delivery_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_invoice_id TEXT NOT NULL,
        invoice_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        issued_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(delivery_receipt_id) REFERENCES delivery_receipts(receipt_id),
        UNIQUE(provider, external_invoice_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS payment_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        invoice_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_transaction_id TEXT NOT NULL,
        transaction_url TEXT NOT NULL,
        gross_amount_cents INTEGER NOT NULL,
        fee_amount_cents INTEGER NOT NULL,
        net_amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        paid_at TEXT NOT NULL,
        settled_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(invoice_receipt_id) REFERENCES invoice_receipts(receipt_id),
        UNIQUE(provider, external_transaction_id)
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


def record_submission(path, opportunity_id, proposal_id, submission, *, now=None):
    """Persist a provider receipt and advance a prepared proposal atomically.

    This records an already completed submission; it does not contact a buyer or
    bypass provider authentication. The proposal must be an artifact already
    stored for this opportunity.
    """
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise ValueError("proposal_id_required")
    if not isinstance(submission, dict):
        raise ValueError("submission_object_required")
    opportunity_id = opportunity_id.strip()
    proposal_id = proposal_id.strip()
    provider = _proposal_text(submission.get("provider"), "submission_provider", 160)
    external_id = _proposal_text(
        submission.get("external_submission_id"), "external_submission_id", 500)
    submission_url = canonical_url(
        _proposal_text(submission.get("submission_url"), "submission_url", 2000))
    if urlsplit(submission_url).scheme != "https":
        raise ValueError("submission_url_https_required")
    submitted_at = parse_time(submission.get("submitted_at"), "submitted_at")
    recorded = now or utc_now()
    if submitted_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("submitted_at_future")

    receipt = {"opportunity_id": opportunity_id, "proposal_id": proposal_id,
               "provider": provider, "external_submission_id": external_id,
               "submission_url": submission_url, "submitted_at": submitted_at.isoformat()}
    serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
    receipt_id = "subr_" + receipt_hash[:24]
    evidence_id = "submission:" + receipt_id
    recorded_at = recorded.isoformat()
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            proposal = connection.execute(
                "SELECT opportunity_id,created_at FROM proposal_artifacts WHERE proposal_id=?",
                (proposal_id,)).fetchone()
            if proposal is None:
                raise ValueError("proposal_not_found")
            if proposal[0] != opportunity_id:
                raise ValueError("proposal_opportunity_mismatch")
            if submitted_at < parse_time(proposal[1], "proposal_created_at"):
                raise ValueError("submission_before_proposal")
            existing = connection.execute(
                "SELECT 1 FROM submission_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
            if row[0] == "submitted" and existing:
                return {"receipt_id": receipt_id, "changed": False, "state": row[0]}
            if row[0] != "proposal_ready":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "proposal_ready", "submitted", evidence_id)
            connection.execute("""INSERT INTO submission_receipts
                (receipt_id,opportunity_id,proposal_id,provider,external_submission_id,
                 submission_url,submitted_at,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id, proposal_id, provider, external_id,
                    submission_url, submitted_at.isoformat(), receipt_hash, recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "submitted"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("submitted", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "proposal_ready", "submitted", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": receipt_id, "changed": True, "state": "submitted"}
    finally:
        connection.close()


def record_response(path, opportunity_id, submission_receipt_id, response, *, now=None):
    """Persist a provider-backed buyer response and advance it atomically."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(submission_receipt_id, str) or not submission_receipt_id.strip():
        raise ValueError("submission_receipt_id_required")
    if not isinstance(response, dict):
        raise ValueError("response_object_required")
    opportunity_id = opportunity_id.strip()
    submission_receipt_id = submission_receipt_id.strip()
    provider = _proposal_text(response.get("provider"), "response_provider", 160)
    external_id = _proposal_text(
        response.get("external_message_id"), "external_message_id", 500)
    message_url = canonical_url(
        _proposal_text(response.get("message_url"), "message_url", 2000))
    if urlsplit(message_url).scheme != "https":
        raise ValueError("message_url_https_required")
    received_at = parse_time(response.get("received_at"), "received_at")
    recorded = now or utc_now()
    if received_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("received_at_future")

    receipt = {"opportunity_id": opportunity_id,
               "submission_receipt_id": submission_receipt_id,
               "provider": provider, "external_message_id": external_id,
               "message_url": message_url, "received_at": received_at.isoformat()}
    serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
    receipt_id = "respr_" + receipt_hash[:24]
    evidence_id = "reply:" + receipt_id
    recorded_at = recorded.isoformat()
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            submission = connection.execute(
                "SELECT opportunity_id,provider,submitted_at FROM submission_receipts WHERE receipt_id=?",
                (submission_receipt_id,)).fetchone()
            if submission is None:
                raise ValueError("submission_receipt_not_found")
            if submission[0] != opportunity_id:
                raise ValueError("submission_opportunity_mismatch")
            if submission[1].casefold() != provider.casefold():
                raise ValueError("response_provider_mismatch")
            if received_at < parse_time(submission[2], "submission_submitted_at"):
                raise ValueError("response_before_submission")
            existing = connection.execute(
                "SELECT 1 FROM response_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
            if row[0] == "response_received" and existing:
                return {"receipt_id": receipt_id, "changed": False, "state": row[0]}
            if row[0] != "submitted":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "submitted", "response_received", evidence_id)
            connection.execute("""INSERT INTO response_receipts
                (receipt_id,opportunity_id,submission_receipt_id,provider,external_message_id,
                 message_url,received_at,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id, submission_receipt_id, provider, external_id,
                    message_url, received_at.isoformat(), receipt_hash, recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "response_received"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("response_received", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "submitted", "response_received", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": receipt_id, "changed": True, "state": "response_received"}
    finally:
        connection.close()


def record_contract(path, opportunity_id, response_receipt_id, contract, *, now=None):
    """Record an externally accepted, authorized contract without accepting it."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(response_receipt_id, str) or not response_receipt_id.strip():
        raise ValueError("response_receipt_id_required")
    if not isinstance(contract, dict):
        raise ValueError("contract_object_required")
    opportunity_id = opportunity_id.strip()
    response_receipt_id = response_receipt_id.strip()
    provider = _proposal_text(contract.get("provider"), "contract_provider", 160)
    external_id = _proposal_text(
        contract.get("external_contract_id"), "external_contract_id", 500)
    contract_url = canonical_url(
        _proposal_text(contract.get("contract_url"), "contract_url", 2000))
    authority_url = canonical_url(_proposal_text(
        contract.get("authority_evidence_url"), "authority_evidence_url", 2000))
    if urlsplit(contract_url).scheme != "https":
        raise ValueError("contract_url_https_required")
    if urlsplit(authority_url).scheme != "https":
        raise ValueError("authority_evidence_url_https_required")
    amount_cents = finite_number(contract, "amount_cents", minimum=1)
    if not amount_cents.is_integer():
        raise ValueError("amount_cents_invalid")
    currency = _proposal_text(contract.get("currency"), "contract_currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("contract_currency_invalid")
    terms_authority = _proposal_text(
        contract.get("terms_authority"), "terms_authority", 80)
    if terms_authority not in {"preapproved_standard_terms", "owner_approved_terms"}:
        raise ValueError("terms_authority_invalid")
    contracted_at = parse_time(contract.get("contracted_at"), "contracted_at")
    recorded = now or utc_now()
    if contracted_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("contracted_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            response = connection.execute("""SELECT rr.opportunity_id,rr.provider,sr.proposal_id,
                rr.received_at
                FROM response_receipts rr JOIN submission_receipts sr
                ON sr.receipt_id=rr.submission_receipt_id WHERE rr.receipt_id=?""",
                (response_receipt_id,)).fetchone()
            if response is None:
                raise ValueError("response_receipt_not_found")
            if response[0] != opportunity_id:
                raise ValueError("response_opportunity_mismatch")
            if response[1].casefold() != provider.casefold():
                raise ValueError("contract_provider_mismatch")
            if contracted_at < parse_time(response[3], "response_received_at"):
                raise ValueError("contract_before_response")
            proposal_id = response[2]
            proposal = json.loads(connection.execute(
                "SELECT artifact_json FROM proposal_artifacts WHERE proposal_id=?",
                (proposal_id,)).fetchone()[0])
            opportunity = json.loads(row[1])
            if int(amount_cents) > proposal["price_cents"]:
                raise ValueError("contract_amount_exceeds_proposal")
            if currency != opportunity["currency"]:
                raise ValueError("contract_currency_mismatch")
            receipt = {"opportunity_id": opportunity_id,
                       "response_receipt_id": response_receipt_id,
                       "proposal_id": proposal_id, "provider": provider,
                       "external_contract_id": external_id, "contract_url": contract_url,
                       "amount_cents": int(amount_cents), "currency": currency,
                       "contracted_at": contracted_at.isoformat(),
                       "terms_authority": terms_authority,
                       "authority_evidence_url": authority_url}
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            receipt_id = "contr_" + receipt_hash[:24]
            evidence_id = "contract:" + receipt_id
            recorded_at = recorded.isoformat()
            existing = connection.execute(
                "SELECT 1 FROM contract_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
            if row[0] == "contracted" and existing:
                return {"receipt_id": receipt_id, "changed": False, "state": row[0]}
            if row[0] != "response_received":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "response_received", "contracted", evidence_id)
            connection.execute("""INSERT INTO contract_receipts
                (receipt_id,opportunity_id,response_receipt_id,proposal_id,provider,
                 external_contract_id,contract_url,amount_cents,currency,contracted_at,
                 terms_authority,authority_evidence_url,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id, response_receipt_id, proposal_id, provider,
                    external_id, contract_url, int(amount_cents), currency,
                    contracted_at.isoformat(), terms_authority, authority_url,
                    receipt_hash, recorded_at))
            opportunity["pipeline_state"] = "contracted"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("contracted", json.dumps(opportunity, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "response_received", "contracted", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": receipt_id, "changed": True, "state": "contracted"}
    finally:
        connection.close()


def start_execution(path, opportunity_id, contract_receipt_id, plan, *, now=None):
    """Persist a bounded delivery plan before marking contracted work executing."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(contract_receipt_id, str) or not contract_receipt_id.strip():
        raise ValueError("contract_receipt_id_required")
    if not isinstance(plan, dict):
        raise ValueError("execution_plan_object_required")
    opportunity_id = opportunity_id.strip()
    contract_receipt_id = contract_receipt_id.strip()
    environment = _proposal_text(plan.get("execution_environment"), "execution_environment", 500)
    deliverables = plan.get("deliverables")
    if not isinstance(deliverables, list) or not 1 <= len(deliverables) <= 20:
        raise ValueError("deliverables_invalid")
    normalized_deliverables = []
    for deliverable in deliverables:
        if not isinstance(deliverable, dict):
            raise ValueError("deliverable_invalid")
        title = _proposal_text(deliverable.get("title"), "deliverable_title", 160)
        description = _proposal_text(
            deliverable.get("description"), "deliverable_description", 2000)
        acceptance = _proposal_text(
            deliverable.get("acceptance_criteria"), "acceptance_criteria", 2000)
        due_at = parse_time(deliverable.get("due_at"), "deliverable_due_at")
        normalized_deliverables.append({"title": title, "description": description,
                                        "acceptance_criteria": acceptance,
                                        "due_at": due_at.isoformat()})
    started_at = parse_time(plan.get("started_at"), "started_at")
    recorded = now or utc_now()
    if started_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("started_at_future")
    if any(parse_time(item["due_at"], "deliverable_due_at") <= started_at
           for item in normalized_deliverables):
        raise ValueError("deliverable_due_at_invalid")

    artifact = {"opportunity_id": opportunity_id,
                "contract_receipt_id": contract_receipt_id,
                "execution_environment": environment,
                "deliverables": normalized_deliverables,
                "started_at": started_at.isoformat()}
    serialized = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    plan_hash = hashlib.sha256(serialized.encode()).hexdigest()
    plan_id = "execp_" + plan_hash[:24]
    evidence_id = "contract:" + contract_receipt_id + ":plan:" + plan_id
    recorded_at = recorded.isoformat()
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            contract = connection.execute(
                "SELECT opportunity_id,contracted_at FROM contract_receipts WHERE receipt_id=?",
                (contract_receipt_id,)).fetchone()
            if contract is None:
                raise ValueError("contract_receipt_not_found")
            if contract[0] != opportunity_id:
                raise ValueError("contract_opportunity_mismatch")
            if started_at < parse_time(contract[1], "contract_contracted_at"):
                raise ValueError("execution_before_contract")
            existing = connection.execute(
                "SELECT 1 FROM execution_plans WHERE plan_id=?", (plan_id,)).fetchone()
            if row[0] == "executing" and existing:
                return {"plan_id": plan_id, "changed": False, "state": row[0]}
            if row[0] != "contracted":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "contracted", "executing", evidence_id)
            connection.execute("""INSERT INTO execution_plans
                (plan_id,opportunity_id,contract_receipt_id,plan_hash,plan_json,started_at,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    plan_id, opportunity_id, contract_receipt_id, plan_hash, serialized,
                    started_at.isoformat(), recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "executing"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("executing", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "contracted", "executing", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"plan_id": plan_id, "changed": True, "state": "executing"}
    finally:
        connection.close()


def pass_qa(path, opportunity_id, execution_plan_id, report, *, now=None):
    """Persist objective passing QA evidence before marking work QA-passed."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(execution_plan_id, str) or not execution_plan_id.strip():
        raise ValueError("execution_plan_id_required")
    if not isinstance(report, dict):
        raise ValueError("qa_report_object_required")
    opportunity_id = opportunity_id.strip()
    execution_plan_id = execution_plan_id.strip()
    artifact_sha256 = _proposal_text(report.get("artifact_sha256"), "artifact_sha256", 64).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("artifact_sha256_invalid")
    tests = report.get("tests")
    if not isinstance(tests, list) or not 1 <= len(tests) <= 100:
        raise ValueError("qa_tests_invalid")
    normalized_tests = []
    for test in tests:
        if not isinstance(test, dict):
            raise ValueError("qa_test_invalid")
        name = _proposal_text(test.get("name"), "qa_test_name", 200)
        if test.get("status") != "passed":
            raise ValueError("qa_test_not_passed")
        evidence_url = canonical_url(
            _proposal_text(test.get("evidence_url"), "qa_evidence_url", 2000))
        if urlsplit(evidence_url).scheme != "https":
            raise ValueError("qa_evidence_url_https_required")
        normalized_tests.append({"name": name, "status": "passed",
                                 "evidence_url": evidence_url})
    completed_at = parse_time(report.get("completed_at"), "qa_completed_at")
    recorded = now or utc_now()
    if completed_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("qa_completed_at_future")

    artifact = {"opportunity_id": opportunity_id,
                "execution_plan_id": execution_plan_id,
                "artifact_sha256": artifact_sha256, "tests": normalized_tests,
                "completed_at": completed_at.isoformat()}
    serialized = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    report_hash = hashlib.sha256(serialized.encode()).hexdigest()
    report_id = "qar_" + report_hash[:24]
    evidence_id = "qa:" + report_id
    recorded_at = recorded.isoformat()
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            plan = connection.execute(
                "SELECT opportunity_id,started_at FROM execution_plans WHERE plan_id=?",
                (execution_plan_id,)).fetchone()
            if plan is None:
                raise ValueError("execution_plan_not_found")
            if plan[0] != opportunity_id:
                raise ValueError("execution_plan_opportunity_mismatch")
            if completed_at < parse_time(plan[1], "execution_started_at"):
                raise ValueError("qa_before_execution")
            existing = connection.execute(
                "SELECT 1 FROM qa_reports WHERE report_id=?", (report_id,)).fetchone()
            if row[0] == "qa_passed" and existing:
                return {"report_id": report_id, "changed": False, "state": row[0]}
            if row[0] != "executing":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "executing", "qa_passed", evidence_id)
            connection.execute("""INSERT INTO qa_reports
                (report_id,opportunity_id,execution_plan_id,artifact_sha256,report_hash,
                 report_json,completed_at,recorded_at) VALUES (?,?,?,?,?,?,?,?)""", (
                    report_id, opportunity_id, execution_plan_id, artifact_sha256,
                    report_hash, serialized, completed_at.isoformat(), recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "qa_passed"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("qa_passed", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "executing", "qa_passed", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"report_id": report_id, "changed": True, "state": "qa_passed"}
    finally:
        connection.close()


def record_delivery(path, opportunity_id, qa_report_id, delivery, *, now=None):
    """Record provider delivery evidence for the exact QA-approved artifact."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(qa_report_id, str) or not qa_report_id.strip():
        raise ValueError("qa_report_id_required")
    if not isinstance(delivery, dict):
        raise ValueError("delivery_object_required")
    opportunity_id = opportunity_id.strip()
    qa_report_id = qa_report_id.strip()
    provider = _proposal_text(delivery.get("provider"), "delivery_provider", 160)
    external_id = _proposal_text(
        delivery.get("external_delivery_id"), "external_delivery_id", 500)
    delivery_url = canonical_url(
        _proposal_text(delivery.get("delivery_url"), "delivery_url", 2000))
    if urlsplit(delivery_url).scheme != "https":
        raise ValueError("delivery_url_https_required")
    artifact_sha256 = _proposal_text(
        delivery.get("artifact_sha256"), "artifact_sha256", 64).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("artifact_sha256_invalid")
    delivered_at = parse_time(delivery.get("delivered_at"), "delivered_at")
    recorded = now or utc_now()
    if delivered_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("delivered_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            qa = connection.execute("""SELECT q.opportunity_id,q.artifact_sha256,q.completed_at,
                    c.provider
                FROM qa_reports q
                JOIN execution_plans e ON e.plan_id=q.execution_plan_id
                JOIN contract_receipts c ON c.receipt_id=e.contract_receipt_id
                WHERE q.report_id=?""", (qa_report_id,)).fetchone()
            if qa is None:
                raise ValueError("qa_report_not_found")
            if qa[0] != opportunity_id:
                raise ValueError("qa_report_opportunity_mismatch")
            if qa[1] != artifact_sha256:
                raise ValueError("delivery_artifact_mismatch")
            if qa[3].casefold() != provider.casefold():
                raise ValueError("delivery_provider_mismatch")
            if delivered_at < parse_time(qa[2], "qa_completed_at"):
                raise ValueError("delivered_before_qa")
            receipt = {"opportunity_id": opportunity_id, "qa_report_id": qa_report_id,
                       "provider": provider, "external_delivery_id": external_id,
                       "delivery_url": delivery_url, "artifact_sha256": artifact_sha256,
                       "delivered_at": delivered_at.isoformat()}
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            receipt_id = "delr_" + receipt_hash[:24]
            evidence_id = "delivery:" + receipt_id
            recorded_at = recorded.isoformat()
            existing = connection.execute(
                "SELECT 1 FROM delivery_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
            if row[0] == "delivered" and existing:
                return {"receipt_id": receipt_id, "changed": False, "state": row[0]}
            if row[0] != "qa_passed":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "qa_passed", "delivered", evidence_id)
            connection.execute("""INSERT INTO delivery_receipts
                (receipt_id,opportunity_id,qa_report_id,provider,external_delivery_id,
                 delivery_url,artifact_sha256,delivered_at,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id, qa_report_id, provider, external_id,
                    delivery_url, artifact_sha256, delivered_at.isoformat(),
                    receipt_hash, recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "delivered"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("delivered", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "qa_passed", "delivered", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": receipt_id, "changed": True, "state": "delivered"}
    finally:
        connection.close()


def record_invoice(path, opportunity_id, delivery_receipt_id, invoice, *, now=None):
    """Record an external invoice tied to verified delivery; never create a charge."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(delivery_receipt_id, str) or not delivery_receipt_id.strip():
        raise ValueError("delivery_receipt_id_required")
    if not isinstance(invoice, dict):
        raise ValueError("invoice_object_required")
    opportunity_id = opportunity_id.strip()
    delivery_receipt_id = delivery_receipt_id.strip()
    provider = _proposal_text(invoice.get("provider"), "invoice_provider", 160)
    external_id = _proposal_text(
        invoice.get("external_invoice_id"), "external_invoice_id", 500)
    invoice_url = canonical_url(
        _proposal_text(invoice.get("invoice_url"), "invoice_url", 2000))
    if urlsplit(invoice_url).scheme != "https":
        raise ValueError("invoice_url_https_required")
    amount_cents = finite_number(invoice, "amount_cents", minimum=1)
    if not amount_cents.is_integer():
        raise ValueError("amount_cents_invalid")
    currency = _proposal_text(invoice.get("currency"), "invoice_currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("invoice_currency_invalid")
    issued_at = parse_time(invoice.get("issued_at"), "issued_at")
    due_at = parse_time(invoice.get("due_at"), "due_at")
    recorded = now or utc_now()
    if issued_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("issued_at_future")
    if due_at <= issued_at:
        raise ValueError("due_at_invalid")

    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            delivery = connection.execute("""SELECT d.opportunity_id,d.provider,d.delivered_at,
                    c.amount_cents,c.currency
                FROM delivery_receipts d
                JOIN qa_reports q ON q.report_id=d.qa_report_id
                JOIN execution_plans e ON e.plan_id=q.execution_plan_id
                JOIN contract_receipts c ON c.receipt_id=e.contract_receipt_id
                WHERE d.receipt_id=?""", (delivery_receipt_id,)).fetchone()
            if delivery is None:
                raise ValueError("delivery_receipt_not_found")
            if delivery[0] != opportunity_id:
                raise ValueError("delivery_opportunity_mismatch")
            if delivery[1].casefold() != provider.casefold():
                raise ValueError("invoice_provider_mismatch")
            if issued_at < parse_time(delivery[2], "delivered_at"):
                raise ValueError("invoice_before_delivery")
            if int(amount_cents) > delivery[3]:
                raise ValueError("invoice_amount_exceeds_contract")
            if currency != delivery[4]:
                raise ValueError("invoice_currency_mismatch")
            receipt = {"opportunity_id": opportunity_id,
                       "delivery_receipt_id": delivery_receipt_id,
                       "provider": provider, "external_invoice_id": external_id,
                       "invoice_url": invoice_url, "amount_cents": int(amount_cents),
                       "currency": currency, "issued_at": issued_at.isoformat(),
                       "due_at": due_at.isoformat()}
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            receipt_id = "invr_" + receipt_hash[:24]
            evidence_id = "invoice:" + receipt_id
            recorded_at = recorded.isoformat()
            existing = connection.execute(
                "SELECT 1 FROM invoice_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
            if row[0] == "invoiced" and existing:
                return {"receipt_id": receipt_id, "changed": False, "state": row[0]}
            if row[0] != "delivered":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "delivered", "invoiced", evidence_id)
            connection.execute("""INSERT INTO invoice_receipts
                (receipt_id,opportunity_id,delivery_receipt_id,provider,external_invoice_id,
                 invoice_url,amount_cents,currency,issued_at,due_at,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id, delivery_receipt_id, provider, external_id,
                    invoice_url, int(amount_cents), currency, issued_at.isoformat(),
                    due_at.isoformat(), receipt_hash, recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "invoiced"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("invoiced", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "delivered", "invoiced", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": receipt_id, "changed": True, "state": "invoiced"}
    finally:
        connection.close()


def record_collected_payment(path, opportunity_id, invoice_receipt_id, payment, *, now=None):
    """Record a settled provider payment linked to an invoice; never initiate a charge."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(invoice_receipt_id, str) or not invoice_receipt_id.strip():
        raise ValueError("invoice_receipt_id_required")
    if not isinstance(payment, dict):
        raise ValueError("payment_object_required")
    opportunity_id = opportunity_id.strip()
    invoice_receipt_id = invoice_receipt_id.strip()
    provider = _proposal_text(payment.get("provider"), "payment_provider", 160)
    external_id = _proposal_text(
        payment.get("external_transaction_id"), "external_transaction_id", 500)
    transaction_url = canonical_url(
        _proposal_text(payment.get("transaction_url"), "transaction_url", 2000))
    if urlsplit(transaction_url).scheme != "https":
        raise ValueError("transaction_url_https_required")
    amounts = {}
    for field, minimum in (("gross_amount_cents", 1), ("fee_amount_cents", 0),
                           ("net_amount_cents", 1)):
        amount = finite_number(payment, field, minimum=minimum)
        if not amount.is_integer():
            raise ValueError(f"{field}_invalid")
        amounts[field] = int(amount)
    if amounts["net_amount_cents"] != (
            amounts["gross_amount_cents"] - amounts["fee_amount_cents"]):
        raise ValueError("payment_net_amount_mismatch")
    currency = _proposal_text(payment.get("currency"), "payment_currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("payment_currency_invalid")
    paid_at = parse_time(payment.get("paid_at"), "paid_at")
    settled_at = parse_time(payment.get("settled_at"), "settled_at")
    recorded = now or utc_now()
    if paid_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("paid_at_future")
    if settled_at < paid_at:
        raise ValueError("settled_before_paid")
    if settled_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("settled_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            invoice = connection.execute("""SELECT opportunity_id,provider,amount_cents,
                    currency,issued_at
                FROM invoice_receipts WHERE receipt_id=?""",
                (invoice_receipt_id,)).fetchone()
            if invoice is None:
                raise ValueError("invoice_receipt_not_found")
            if invoice[0] != opportunity_id:
                raise ValueError("payment_opportunity_mismatch")
            if invoice[1].casefold() != provider.casefold():
                raise ValueError("payment_provider_mismatch")
            if amounts["gross_amount_cents"] != invoice[2]:
                raise ValueError("payment_amount_mismatch")
            if currency != invoice[3]:
                raise ValueError("payment_currency_mismatch")
            if paid_at < parse_time(invoice[4], "invoice_issued_at"):
                raise ValueError("payment_before_invoice")
            receipt = {"opportunity_id": opportunity_id,
                       "invoice_receipt_id": invoice_receipt_id,
                       "provider": provider, "external_transaction_id": external_id,
                       "transaction_url": transaction_url, **amounts,
                       "currency": currency, "paid_at": paid_at.isoformat(),
                       "settled_at": settled_at.isoformat()}
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            receipt_id = "payr_" + receipt_hash[:24]
            evidence_id = "verified_payment:" + receipt_id
            recorded_at = recorded.isoformat()
            existing = connection.execute(
                "SELECT 1 FROM payment_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
            if row[0] == "collected" and existing:
                return {"receipt_id": receipt_id, "changed": False, "state": row[0],
                        "net_amount_cents": amounts["net_amount_cents"]}
            if row[0] != "invoiced":
                raise ValueError("pipeline_state_conflict")
            tid = transition_id(opportunity_id, "invoiced", "collected", evidence_id)
            connection.execute("""INSERT INTO payment_receipts
                (receipt_id,opportunity_id,invoice_receipt_id,provider,external_transaction_id,
                 transaction_url,gross_amount_cents,fee_amount_cents,net_amount_cents,currency,
                 paid_at,settled_at,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id, invoice_receipt_id, provider, external_id,
                    transaction_url, amounts["gross_amount_cents"], amounts["fee_amount_cents"],
                    amounts["net_amount_cents"], currency, paid_at.isoformat(),
                    settled_at.isoformat(), receipt_hash, recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "collected"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("collected", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "invoiced", "collected", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": receipt_id, "changed": True, "state": "collected",
                "net_amount_cents": amounts["net_amount_cents"]}
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
    if to_state == "proposal_ready":
        raise ValueError("proposal_artifact_required")
    if to_state == "submitted":
        raise ValueError("submission_receipt_required")
    if to_state == "response_received":
        raise ValueError("response_receipt_required")
    if to_state == "contracted":
        raise ValueError("contract_receipt_required")
    if to_state == "executing":
        raise ValueError("execution_plan_required")
    if to_state == "qa_passed":
        raise ValueError("qa_report_required")
    if to_state == "delivered":
        raise ValueError("delivery_receipt_required")
    if to_state == "invoiced":
        raise ValueError("invoice_receipt_required")
    if to_state == "collected":
        raise ValueError("payment_receipt_required")
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
                      action_mode=excluded.action_mode,
                      pipeline_state=opportunities.pipeline_state,
                      observed_at=excluded.observed_at,
                      payload_json=json_set(excluded.payload_json, '$.pipeline_state',
                                            opportunities.pipeline_state),
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
