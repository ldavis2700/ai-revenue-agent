#!/usr/bin/env python3
"""Fictional, offline creative workflow handoff; never sends or publishes anything.

Human confirmations are recorded as input claims, not independently authenticated approvals.
"""
import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

TRACKS = frozenset({"ad", "funnel"})


def https_url(value):
    if not isinstance(value, str):
        return False
    try:
        p = urlparse(value)
    except ValueError:
        return False
    return p.scheme == "https" and bool(p.hostname) and "." in p.hostname and not p.username and not p.password and not p.fragment and p.port in (None, 443)


def money(value):
    if isinstance(value, bool) or not isinstance(value, str):
        return None
    try:
        n = Decimal(value)
        if not n.is_finite() or n < 0 or n.as_tuple().exponent < -2:
            return None
        return n
    except (InvalidOperation, ValueError):
        return None


def review(data):
    """Create a source-bound, per-client, per-track manual review packet."""
    if not isinstance(data, dict):
        raise ValueError("Input must be an object")
    client = data.get("client_id")
    context = data.get("approved_client_context")
    items = data.get("work_items")
    if not isinstance(client, str) or not client.strip() or not isinstance(context, dict) or not isinstance(items, list):
        raise ValueError("client_id, approved_client_context and work_items required")
    context_ok = (context.get("client_id") == client and context.get("approved") is True
                  and isinstance(context.get("version"), str) and bool(context["version"].strip())
                  and isinstance(context.get("approved_by"), str) and bool(context["approved_by"].strip())
                  and isinstance(context.get("source_urls"), list) and bool(context["source_urls"])
                  and all(https_url(u) for u in context["source_urls"]))
    results = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("work item must be an object")
        issues = []
        item_id, track = item.get("id"), item.get("track")
        if not isinstance(item_id, str) or not item_id.strip() or item_id in seen:
            issues.append("missing_or_duplicate_work_id")
        if isinstance(item_id, str):
            seen.add(item_id)
        if track not in TRACKS:
            issues.append("unsupported_track")
        if item.get("client_id") != client or item.get("context_version") != context.get("version") or not context_ok:
            issues.append("approved_client_context_not_verified")
        for field in ("strategy_owner", "production_owner", "review_owner", "brief"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                issues.append("missing_" + field)
        source_urls = item.get("source_urls")
        if not isinstance(source_urls, list) or not source_urls or not all(https_url(u) for u in source_urls):
            issues.append("source_provenance_missing_or_unsafe")
        costs = item.get("tool_costs")
        total = Decimal("0")
        if not isinstance(costs, list) or not costs:
            issues.append("itemized_costs_missing")
        else:
            for cost in costs:
                if not isinstance(cost, dict) or not isinstance(cost.get("name"), str) or not cost["name"].strip() or not https_url(cost.get("pricing_source_url")):
                    issues.append("cost_source_missing")
                    break
                amount = money(cost.get("usd"))
                if amount is None:
                    issues.append("cost_unknown_or_invalid")
                    break
                total += amount
        if item.get("strategy_reviewed") is not True:
            issues.append("strategy_human_review_pending")
        if item.get("creative_reviewed") is not True:
            issues.append("creative_human_review_pending")
        blob = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        results.append({"id": item_id, "track": track, "status": "ready_for_manual_handoff" if not issues else "blocked_pending_evidence_or_review",
                        "blockers": issues, "artifact_sha256": hashlib.sha256(blob).hexdigest(),
                        "itemized_tool_cost_usd": str(total.quantize(Decimal(".01"))) if not any(x in issues for x in ("itemized_costs_missing", "cost_source_missing", "cost_unknown_or_invalid")) else None,
                        "next_actor": item.get("review_owner") if not issues else "named human owners must resolve blockers", "external_action_allowed": False})
    return {"client_id": client, "client_context_is_input_claim_only": True,
            "mode": "fictional_offline_handoff", "reviewed_items": len(results), "work_items": results,
            "external_action_allowed": False, "collected_revenue_usd": None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    a = p.parse_args()
    with open(a.input, encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(review(data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
