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
    if not isinstance(urls,list) or not urls or any(not _source_url(u) for u in urls):
        reasons.append("grounded_source_urls_required")
    if not isinstance(candidate["buyer_evidence"],str) or not candidate["buyer_evidence"].strip():
        reasons.append("real_buyer_evidence_required")
    for evidence_key in ("buyer_evidence_url", "payment_rail_evidence_url"):
        value=candidate[evidence_key]
        if not _source_url(value):
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
    # Stripe is allowed for APEX-only *preparation*, not public checkout or sending.
    # All evidence booleans are operator supplied, never payment or delivery proof.
    rail_label = str(candidate["payment_rail_name"]).casefold().replace("non-stripe", "").replace("non stripe", "")
    if "stripe" in rail_label:
        if str(candidate.get("property_id", "")).strip() != "003":
            reasons.append("apex_stripe_property_scope_required")
        if candidate.get("apex_stripe_provider_verified") is not True:
            reasons.append("apex_stripe_provider_verification_required")
        if candidate.get("stripe_buyer_reconciliation_verified") is not True:
            reasons.append("stripe_buyer_reconciliation_required")
        if candidate.get("public_checkout_paused") is not True:
            reasons.append("public_checkout_must_remain_paused")
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
    if not _source_url(qa):
        reasons.append("delivery_qa_receipt_required")
    if candidate.get("actual_buyer_acceptance_verified") is not True:
        reasons.append("real_buyer_acceptance_not_verified")
    return {"state":"acceptance_evidence_supplied" if not reasons else "preparation_only",
            "missing":reasons,"verified_by_this_code":False,
            "external_delivery_performed":False,"settled_payment_verified":False}


def execution_review(candidate, evaluation, now):
    """Require a bounded, falsifiable experiment before shortlisting new work.

    Forecasts and source links are supplied by an operator, never receipts.
    This ranks reversible preparation; it cannot authorize external execution.
    """
    plan = candidate.get("execution_plan")
    reasons = []
    expected = rate = None
    cash_days = None
    if not isinstance(plan, dict):
        reasons.append("execution_plan_required")
    else:
        for key in ("hypothesis", "customer_segment", "acceptance_test",
                    "measurement_method", "stop_rule", "next_action",
                    "probability_basis"):
            if not isinstance(plan.get(key), str) or not plan[key].strip():
                reasons.append(key + "_required")
        if plan.get("success_metric") not in (
            "qualified_opt_in_requests", "buyer_accepted_deliveries", "settled_paid_deliveries"
        ):
            reasons.append("customer_outcome_metric_required")
        for key in ("baseline", "target"):
            value = plan.get(key)
            if type(value) is not int or value < 0:
                reasons.append("nonnegative_integer_" + key + "_required")
        if not any(r.startswith("nonnegative_integer_") for r in reasons):
            if plan["target"] <= plan["baseline"]:
                reasons.append("target_must_exceed_baseline")
        for key, low, high in (("minimum_sample_size", 1, 1000000),
                               ("estimated_total_minutes", 1, 525600),
                               ("estimated_days_to_cash", 1, 365),
                               ("success_probability_bps", 0, 10000)):
            value = plan.get(key)
            if type(value) is not int or not low <= value <= high:
                reasons.append(key + "_invalid")
        if type(plan.get("max_new_spend_cents")) is not int or plan["max_new_spend_cents"] != 0:
            reasons.append("zero_new_spend_required")
        if not _source_url(plan.get("probability_evidence_url")):
            reasons.append("probability_evidence_required")
        try:
            deadline = datetime.fromisoformat(plan["review_at"].replace("Z", "+00:00"))
            if deadline.tzinfo is None or not timedelta(0) < deadline - now <= timedelta(days=14):
                reasons.append("review_must_be_within_fourteen_days")
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            reasons.append("invalid_review_time")
        if not reasons and evaluation.get("estimated_contribution_cents") is not None:
            # Charge all estimated costs even in the failure case. Do not just
            # multiply the successful-case margin by an optimistic probability.
            costs = sum(candidate[k] for k in (
                "estimated_direct_cost_cents", "estimated_support_cost_cents",
                "estimated_platform_fee_cents"))
            expected = (candidate["estimated_revenue_cents"] * plan["success_probability_bps"]
                        // 10000 - costs)
            rate = expected * 60 // plan["estimated_total_minutes"]
            cash_days = plan["estimated_days_to_cash"]
            if expected <= 0:
                reasons.append("no_positive_risk_adjusted_contribution")
    if evaluation["learning"]["state"] != "documented_current":
        reasons.append("refresh_learning_before_shortlisting")
    if evaluation["state"] != "prepare_only":
        reasons.append("resolve_preparation_blockers")
    return {"state": "documented_for_preparation" if not reasons else "needs_work",
            "reasons": reasons, "estimated_expected_contribution_cents": expected,
            "estimated_expected_cents_per_hour": rate,
            "estimated_days_to_cash": cash_days,
            "estimate_is_collected_cash": False, "source_contents_verified": False,
            "external_actions_authorized": False, "expertise_demonstrated": False}


def weekly_report(candidates,now=None):
    if not isinstance(candidates,list):raise ValueError("candidates must be a list")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    # Do not silently drop the 31st candidate or let duplicate models occupy
    # both experiment slots. Reject the batch so operators can correct it.
    if len(candidates) > 30:
        raise ValueError("review at most 30 candidates per batch")
    seen = set()
    results = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("each candidate must be an object")
        model_id = item.get("model_id")
        if not isinstance(model_id, str) or not model_id.strip() or model_id in seen:
            raise ValueError("model_id must be a unique nonempty string")
        seen.add(model_id)
        result = evaluate(item, now)
        result["execution"] = execution_review(item, result, now)
        results.append(result)
    eligible=[r for r in results if r["execution"]["state"]=="documented_for_preparation"]
    eligible.sort(key=lambda x:(-x["execution"]["estimated_expected_cents_per_hour"],
                                x["execution"]["estimated_days_to_cash"], x["model_id"]))
    return {"research_type":"weekly_ai_models","evidence_state":"operator_supplied_unverified_sources",
            "ranked_preparation_candidates":eligible[:2],
            "all_evaluations":results,"selected_experiments_limit":2,
            "learning_refresh_queue":[{"model_id":r["model_id"],
                                       "topics":r["learning"]["next_learning_topics"]}
                                      for r in results if r["learning"]["next_learning_topics"]],
            "execution_preparation_queue":[{"model_id":r["model_id"],
                                            "requirements":r["execution"]["reasons"]}
                                           for r in results if r["execution"]["reasons"]],
            "ranking_basis":"estimated_expected_contribution_per_total_work_hour_then_days_to_cash",
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
