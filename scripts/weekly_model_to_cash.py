#!/usr/bin/env python3
"""Evidence-gated weekly AI model-to-cash selection. No contact, charges or contracts."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from urllib.parse import urlsplit

# Review intervals are operating defaults, not claims that a market stays stable.
# A known material change invalidates a topic immediately, regardless of age.
LEARNING_TOPICS = {
    "customer_demand": 7,
    "pricing_and_fees": 7,
    "platform_rules_and_rights": 7,
    "acquisition_and_consent": 7,
    "delivery_and_qa": 30,
    "collection_and_unit_economics": 7,
    "retention_and_failure_lessons": 30,
}


def learning_review(candidate, now=None):
    """Return an actionable refresh checklist; never infer expertise from claims.

    Evidence remains operator supplied. This pure function neither fetches URLs
    nor changes permission to fulfill existing funded customer obligations.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    supplied = candidate.get("learning_evidence", {})
    if not isinstance(supplied, dict):
        supplied = {}
    topics = []
    for topic, days in LEARNING_TOPICS.items():
        item = supplied.get(topic)
        reasons = []
        due_at = None
        if not isinstance(item, dict):
            reasons.append("missing_topic")
        else:
            for key in ("finding", "next_action"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    reasons.append("missing_" + key)
            sources = item.get("source_urls")
            if not isinstance(sources, list) or not sources or not all(_source_url(u) for u in sources):
                reasons.append("source_urls_required")
            try:
                checked = datetime.fromisoformat(item["checked_at"].replace("Z", "+00:00"))
                if checked.tzinfo is None or checked.utcoffset() is None:
                    raise ValueError("naive time")
                due = checked + timedelta(days=days)
                due_at = due.isoformat()
                if checked > now:
                    reasons.append("future_check")
                elif now >= due:
                    reasons.append("stale_check")
            except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
                reasons.append("invalid_check_time")
            if item.get("material_change", False) is not False:
                reasons.append("material_change_requires_review")
        topics.append({"topic": topic, "state": "refresh_required" if reasons else "documented_current",
                       "reasons": reasons, "refresh_due_at": due_at})
    pending = [t["topic"] for t in topics if t["state"] == "refresh_required"]
    return {"state": "refresh_required" if pending else "documented_current",
            "topics": topics, "next_learning_topics": pending,
            "source_contents_verified": False, "expertise_demonstrated": False,
            "external_actions_authorized": False}


def _source_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname)
                and url.username is None and url.password is None)
    except ValueError:
        return False

REQUIRED = ("model_id", "observed_at", "source_urls", "buyer_evidence",
            "deliverable", "delivery_capabilities_verified", "demand_channel",
            "contact_permission_verified", "payment_rail_verified",
            "payment_rail_name", "refund_support_defined",
            "estimated_revenue_cents", "estimated_direct_cost_cents", "estimated_support_cost_cents",
            "estimated_platform_fee_cents", "external_credentials_verified",
            "buyer_evidence_url", "payment_rail_evidence_url")
ALLOWED_URL_PREFIXES = ("https://",)

def evaluate(candidate, now=None):
    now=now or datetime.now(timezone.utc)
    missing=[x for x in REQUIRED if x not in candidate]
    if missing:
        return {"model_id":candidate.get("model_id","unknown"),"state":"insufficient_evidence",
                "learning":learning_review(candidate, now),
                "reasons":["missing:"+x for x in missing],"next_action":"Collect missing actual buyer/collection/delivery evidence"}
    reasons=[]
    try:
        when=datetime.fromisoformat(candidate["observed_at"].replace("Z","+00:00"))
        if when.tzinfo is None or not timedelta(0)<=now-when<=timedelta(days=14):
            reasons.append("evidence_stale_or_future")
    except (TypeError,ValueError,AttributeError):
        reasons.append("invalid_observation_time")
    urls=candidate["source_urls"]
    if not isinstance(urls,list) or not urls or any(not isinstance(u,str) or not u.startswith(ALLOWED_URL_PREFIXES) for u in urls):
        reasons.append("grounded_source_urls_required")
    if not isinstance(candidate["buyer_evidence"],str) or not candidate["buyer_evidence"].strip():
        reasons.append("real_buyer_evidence_required")
    for evidence_key in ("buyer_evidence_url", "payment_rail_evidence_url"):
        value=candidate[evidence_key]
        if not isinstance(value,str) or not value.startswith("https://"):
            reasons.append(evidence_key+"_required")
    if not isinstance(candidate["deliverable"],str) or len(candidate["deliverable"].strip())<12:
        reasons.append("specific_deliverable_required")
    for key in ("delivery_capabilities_verified","contact_permission_verified",
                "payment_rail_verified","refund_support_defined"):
        if candidate[key] is not True:reasons.append(key+"_required")
    if not isinstance(candidate["demand_channel"],str) or not candidate["demand_channel"].strip():
        reasons.append("permitted_demand_channel_required")
    if not isinstance(candidate["payment_rail_name"],str) or not candidate["payment_rail_name"].strip():
        reasons.append("named_authorized_payment_rail_required")
    if str(candidate["payment_rail_name"]).lower().strip()=="stripe":
        reasons.append("stripe_paused")
    for key in ("estimated_revenue_cents","estimated_direct_cost_cents",
                "estimated_support_cost_cents","estimated_platform_fee_cents"):
        if type(candidate[key]) is not int or candidate[key]<0:
            reasons.append("nonnegative_integer_"+key+"_required")
    if candidate.get("spend_required",False) is not False:reasons.append("spend_not_authorized")
    if candidate.get("contract_acceptance_required",False) is not False:reasons.append("contract_approval_required")
    if candidate.get("unsolicited_outreach_required",False) is not False:reasons.append("unsolicited_outreach_not_authorized")
    if candidate["external_credentials_verified"] is not True:reasons.append("missing_authorized_access")
    if any(r.startswith("nonnegative_integer_") for r in reasons):
        contribution=None
    else:
        contribution=(candidate["estimated_revenue_cents"]-candidate["estimated_direct_cost_cents"]
                      -candidate["estimated_support_cost_cents"]-candidate["estimated_platform_fee_cents"])
        if contribution<=0:reasons.append("no_positive_estimated_contribution")
    return {"model_id":candidate["model_id"],"state":"prepare_only" if not reasons else "blocked",
            "reasons":reasons,"estimated_contribution_cents":contribution,
            "estimate_is_collected_cash":False,"source_urls_operator_verified":False,
            "next_action":("Prepare a truthful scoped offer and tested delivery artifact; validate with a consenting buyer"
                           if not reasons else "Resolve the listed blockers and recheck current provider evidence"),
            "external_action_executed":False,"receipt_verified":False,
            "learning":learning_review(candidate, now),
            "recreation":recreation_gate(candidate)}

def recreation_gate(candidate):
    """Judge reproduction evidence without treating a public business idea as licensable IP.

    This is a *documentation gate* only; the operator must independently
    verify the original assets and checks against the trusted provider.
    """
    reasons=[]
    if candidate.get("copied_proprietary_material") is not False:
        reasons.append("independent_original_implementation_required")
    if candidate.get("rights_verified") is not True:
        reasons.append("rights_review_required")
    artifact=candidate.get("delivery_artifact_sha256")
    if not isinstance(artifact,str) or len(artifact)!=64 or any(c not in "0123456789abcdef" for c in artifact):
        reasons.append("immutable_delivery_artifact_required")
    qa=candidate.get("delivery_qa_evidence_url")
    if not isinstance(qa,str) or not qa.startswith("https://"):
        reasons.append("delivery_qa_receipt_required")
    if candidate.get("actual_buyer_acceptance_verified") is not True:
        reasons.append("real_buyer_acceptance_not_verified")
    return {"state":"acceptance_evidence_supplied" if not reasons else "preparation_only",
            "missing":reasons,"verified_by_this_code":False,
            "external_delivery_performed":False,"settled_payment_verified":False}


def weekly_report(candidates,now=None):
    if not isinstance(candidates,list):raise ValueError("candidates must be a list")
    results=[evaluate(item,now) for item in candidates[:30]]
    eligible=[r for r in results if r["state"]=="prepare_only"]
    eligible.sort(key=lambda x:x["estimated_contribution_cents"],reverse=True)
    return {"research_type":"weekly_ai_models","evidence_state":"operator_supplied_unverified_sources",
            "ranked_preparation_candidates":eligible[:2],
            "all_evaluations":results,"selected_experiments_limit":2,
            "learning_refresh_queue":[{"model_id":r["model_id"],
                                       "topics":r["learning"]["next_learning_topics"]}
                                      for r in results if r["learning"]["next_learning_topics"]],
            "verified_collected_revenue":"unknown",
            "allowed_actions":"research_and_reversible_preparation_only",
            "automatic_spend":False,"automatic_contracts":False,
            "automatic_unsolicited_outreach":False,
            "automatic_production_deploy":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True)
    a=p.parse_args()
    print(json.dumps(weekly_report(json.loads(Path(a.evidence).read_text())),indent=2))

if __name__=="__main__":
    main()
