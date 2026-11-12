"""Offline, consent-first Revenue Rescue opportunity preparation.

Never contacts customers, charges cards or asserts revenue. Standard-library only.
Input JSON is a list of observed prospects; output is a review queue.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

OFFER = "APEX Revenue Rescue — $99 Inquiry-to-Booking Quickstart"
ALLOWED = {"inbound_request", "opt_in", "platform_authorized"}
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_ROWS = 1000


def qualify(prospect):
    if not isinstance(prospect, dict):
        return {"status": "rejected", "reason": "invalid_record"}
    name = str(prospect.get("business_name", "")).strip()[:120]
    url = str(prospect.get("evidence_url", "")).strip()
    observation = str(prospect.get("observable_issue", "")).strip()
    source = str(prospect.get("contact_permission", "")).strip()
    email = str(prospect.get("contact_email", "")).strip()
    parsed = urlparse(url)
    if not name or not url or not observation:
        return {"status": "rejected", "reason": "missing_observation"}
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.count("."):
        return {"status": "rejected", "reason": "invalid_evidence_url"}
    if source not in ALLOWED or not EMAIL.fullmatch(email):
        return {"status": "review_only", "reason": "no_verified_contact_permission",
                "business_name": name, "evidence_url": url}
    if len(observation) > 350:
        return {"status": "rejected", "reason": "oversized_observation"}
    return {"status": "draft_ready", "business_name": name,
            "evidence_url": url, "observable_issue": observation,
            "contact_permission": source, "contact_email": email,
            "offer": OFFER,
            "draft": (
                f"Hello, I reviewed the publicly available information for {name}. "
                "Would a simple mobile-friendly booking-request form and inquiry tracker "
                "be useful? Our proposed one-time $99 pilot includes one request form, "
                "one business-controlled destination and a tested handoff. "
                "This does not guarantee new customers or confirm appointments. "
                "If you're interested, I can share the exact scope for your review."
            ),
            "sent": False, "paid": False, "collected_usd": 0}


def prepare(records):
    if not isinstance(records, list) or len(records) > MAX_ROWS:
        raise ValueError("Expected a list of at most 1000 prospects")
    results, seen = [], set()
    for prospect in records:
        result = qualify(prospect)
        if result["status"] == "draft_ready":
            key = (result["business_name"].casefold(), result["contact_email"].casefold())
            if key in seen:
                result = {"status": "rejected", "reason": "duplicate_contact"}
            else:
                seen.add(key)
        results.append(result)
    return {"results": results, "sent_count": 0, "collected_usd": 0,
            "draft_ready_count": sum(r["status"] == "draft_ready" for r in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("Source and destination must differ")
    records = json.loads(args.source.read_text(encoding="utf-8"))
    output = prepare(records)
    with args.destination.open("x", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"Prepared {output['draft_ready_count']} review-only drafts; 0 sends; $0 collected")


if __name__ == "__main__":
    main()
