"""Offline, synthetic-first support triage demonstration; never sends messages."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_ORDER = re.compile(r"\b(?:order|order\s*number|order\s*id)\s*(?:#|:|-)?\s*([A-Z]{0,3}-?\d{5,10})\b", re.IGNORECASE)
_TOPICS = (
    ("billing", ("charged twice", "double charged", "incorrect charge", "billing")),
    ("refund", ("refund", "return", "money back")),
    ("damage", ("damaged", "broken", "defective")),
    ("shipping", ("tracking", "shipment", "shipped", "delivery", "where is my order", "late order")),
    ("cancellation", ("cancel", "cancellation")),
)
# Conservative review hints only; all messages still require human approval.
_URGENT = re.compile(
    r"\b(fraud|identity theft|security breach|unsafe|charged twice|double charged|"
    r"hacked|compromised|account takeover|data breach|unauthorized|chargeback|"
    r"product safety|safety hazard|injur(?:y|ies)|allergic reaction|poisoned|"
    r"medical emergency|fire hazard|battery fire|on fire|caught fire|smoking|"
    r"overheat(?:ing|ed|s)?|burn(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)
_DRAFTS = {
    "billing": "Thanks for contacting us about a billing concern. A team member will review the details and respond through the approved support channel.",
    "refund": "Thanks for reaching out about a return or refund. Our team will review the request against the applicable policy before replying.",
    "damage": "Thanks for letting us know about the product issue. A team member will review the details before advising on possible next steps.",
    "shipping": "Thanks for checking on an order. A team member will review the available shipping details and follow up.",
    "cancellation": "Thanks for your cancellation request. A team member will check the order status and applicable policy before confirming anything.",
    "other": "Thanks for contacting support. A team member will review your question and follow up.",
}


def triage(ticket: dict[str, Any]) -> dict[str, Any]:
    """Return an internal review-only record with no customer body or direct identifiers."""
    if not isinstance(ticket, dict):
        raise ValueError("Ticket must be an object")
    text = ticket.get("message")
    if not isinstance(text, str) or not text.strip() or len(text) > 20_000:
        raise ValueError("Message must contain 1 to 20000 characters")
    if ticket.get("synthetic") is not True and ticket.get("permitted_internal_use") is not True:
        raise PermissionError("Real support messages require verified internal-use permission")
    source_id = ticket.get("id")
    if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", source_id):
        raise ValueError("A safe opaque ticket id is required")
    folded = text.casefold()
    topic = next((name for name, keywords in _TOPICS if any(word in folded for word in keywords)), "other")
    urgent = bool(_URGENT.search(text))
    match = _ORDER.search(text)
    order_ref = ("***" + match.group(1)[-4:]) if match else None
    language = ticket.get("language")
    if language not in ("en", "es", "fr"):
        language = "requires_human_identification"
    return {
        "ticket_id": source_id,
        "topic_hint": topic,
        "urgency_hint": "review_soon" if urgent else "standard_review",
        "language_hint": language,
        "sentiment_hint": "not_inferred_offline",
        "order_reference_masked": order_ref,
        "internal_queue": "billing_review" if topic == "billing" else "support_review",
        "draft_for_review": _DRAFTS[topic],
        "human_approval_required": True,
        "customer_send_enabled": False,
        "status": "internal_draft_only",
    }


def build_review_queue(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(tickets, list) or len(tickets) > 1000:
        raise ValueError("Expected at most 1000 tickets")
    rows = [triage(ticket) for ticket in tickets]
    ids = [row["ticket_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate ticket id; reconcile before any retry")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline, review-only support triage demonstration")
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    result = build_review_queue(source)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Prepared {len(result)} internal drafts; customer send disabled")


if __name__ == "__main__":
    main()
