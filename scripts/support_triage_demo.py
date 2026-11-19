#!/usr/bin/env python3
"""Synthetic-only, deterministic customer-support triage reference implementation.

Offline demonstration, NOT a production helpdesk integration. No persistence,
network calls, credentials, message delivery, or client-data processing.
Every suggested reply is strictly pending human review.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Literal

Topic = Literal["billing", "refund", "shipping", "order", "other"]
Urgency = Literal["normal", "high"]

TOPIC_RULES: tuple[tuple[Topic, re.Pattern[str]], ...] = (
    ("refund", re.compile(r"\b(refund|return|chargeback)\b", re.I)),
    ("billing", re.compile(r"\b(invoice|payment|charged|billing|credit card)\b", re.I)),
    ("shipping", re.compile(r"\b(delivery|deliver|delayed|shipping|shipment|tracking)\b", re.I)),
    ("order", re.compile(r"\b(order|cancel|item|product)\b", re.I)),
)
HIGH_URGENCY = re.compile(
    r"\b(fraud|stolen|unauthorized|charged twice|chargeback|urgent|immediately|lost package|compromised|hacked|account takeover|data breach)\b",
    re.I,
)
ORDER_NUMBER = re.compile(
    r"\b(?:order\s*(?:number|no\.?|#|id)?\s*[:#-]?\s*|#)([A-Z0-9][A-Z0-9-]{3,18})\b",
    re.I,
)


@dataclass(frozen=True)
class PreparedTicket:
    ticket_id: str
    topic: Topic
    urgency: Urgency
    language: str
    order_number: str | None
    internal_route: str
    suggested_reply: str
    approval_state: Literal["pending_human_review"] = "pending_human_review"
    auto_sent: Literal[False] = False
    needs_human_review: Literal[True] = True


def _order_number(message: str) -> str | None:
    for match in ORDER_NUMBER.finditer(message):
        candidate = match.group(1).upper()
        if any(char.isdigit() for char in candidate):
            return candidate
    return None


def prepare_ticket(ticket_id: str, message: str) -> PreparedTicket:
    """Prepare a draft for internal review without outbound side effects.

    Language remains unverified without an actual language detector. This
    deliberately never infers order status, refund decisions or delivery dates.
    """
    if not isinstance(ticket_id, str) or not ticket_id.strip() or len(ticket_id) > 80:
        raise ValueError("ticket_id must be a nonempty identifier of <=80 characters")
    if not isinstance(message, str) or not message.strip() or len(message) > 20000:
        raise ValueError("message must be nonempty and <=20000 characters")
    topic: Topic = "other"
    for candidate, pattern in TOPIC_RULES:
        if pattern.search(message):
            topic = candidate
            break
    urgency: Urgency = "high" if HIGH_URGENCY.search(message) else "normal"
    order_no = _order_number(message)
    route = (
        "human_escalation" if urgency == "high" else
        "billing_review" if topic in ("refund", "billing") else
        "fulfillment_review" if topic in ("shipping", "order") else
        "general_support_review"
    )
    draft = (
        "Thank you for contacting us. I understand your concern. "
        "A member of our support team will review your request and confirm "
        "the next steps."
    )
    return PreparedTicket(ticket_id.strip(), topic, urgency, "unverified",
                          order_no, route, draft)


def safe_audit_event(item: PreparedTicket) -> dict[str, str | bool]:
    """Minimal event without customer message, email, name or an order number."""
    return {
        # No raw, reversible, or unsalted hashed customer-supplied identifier.
        "topic": item.topic,
        "urgency": item.urgency,
        "internal_route": item.internal_route,
        "approval_state": item.approval_state,
        "auto_sent": item.auto_sent,
    }


def demo() -> list[dict[str, object]]:
    # Invented examples only, never past client delivery or measured accuracy.
    fixtures = [
        ("DEMO-001", "My order #AB-10293 shipping is delayed."),
        ("DEMO-002", "Urgent: I was charged twice for order ID ZX9901."),
        ("DEMO-003", "Can you help with a product question?"),
    ]
    return [asdict(prepare_ticket(ticket_id, body)) for ticket_id, body in fixtures]


if __name__ == "__main__":
    print(json.dumps({"label": "SYNTHETIC_DEMO_NOT_CLIENT_DELIVERY",
                      "records": demo()}, indent=2))
