#!/usr/bin/env python3
"""Compliance-gated vacant-land research and dry-run scoring.

This module only evaluates caller-supplied, source-backed parcel records. It
does not scrape, contact owners or buyers, advertise property, create or sign a
contract, move money, or claim projected margin as revenue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "land_research_policies.json"
DEFAULT_STALE_DAYS = 30

ALLOWED_SOURCE_TYPES = {
    "county_assessor", "county_recorder", "government_open_data",
    "licensed_api", "owner_authorized_feed",
}
REQUIRED_LEGAL_CHECKS = {
    "licensing", "marketing", "assignment", "contracts",
    "telemarketing", "disclosures",
}
REQUIRED_DUE_DILIGENCE = {
    "zoning", "use_restrictions", "legal_road_access", "easements",
    "utilities", "flood", "wetlands", "unpaid_taxes", "liens",
    "title_evidence_url", "title_flags",
}


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def finite_number(value: Any, field: str, *, minimum: float = 0,
                  maximum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field}_invalid")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}_invalid") from exc
    if not math.isfinite(number) or number < minimum or (
            maximum is not None and number > maximum):
        raise ValueError(f"{field}_invalid")
    return number


def https_url(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field}_invalid")
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{field}_invalid")
    return value


def _valid_https(value: Any) -> bool:
    try:
        https_url(value, "url")
        return True
    except ValueError:
        return False


def load_policy(path: str | Path = DEFAULT_POLICY) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        policy = json.load(handle)
    if policy.get("default_status") != "QUARANTINED":
        raise ValueError("default_status_must_be_quarantined")
    if not isinstance(policy.get("jurisdictions"), dict):
        raise ValueError("jurisdictions_must_be_object")
    return policy


def jurisdiction_gate(policy: dict[str, Any], jurisdiction: str,
                      now: datetime | None = None) -> tuple[bool, list[str]]:
    entry = policy.get("jurisdictions", {}).get(jurisdiction.upper())
    if not isinstance(entry, dict):
        return False, ["jurisdiction_quarantined"]
    reasons: list[str] = []
    if entry.get("status") != "RESEARCH_ONLY_APPROVED":
        reasons.append("jurisdiction_quarantined")
    if entry.get("human_legal_review") is not True:
        reasons.append("human_legal_review_missing")
    current = _now(now)
    try:
        reviewed_at = parse_time(entry.get("reviewed_at"), "legal_reviewed_at")
        expires_at = parse_time(entry.get("expires_at"), "legal_expires_at")
        if reviewed_at > current + timedelta(minutes=5):
            reasons.append("legal_review_in_future")
        if expires_at <= current:
            reasons.append("legal_review_expired")
    except ValueError as exc:
        reasons.append(str(exc))
    if not str(entry.get("reviewer") or "").strip():
        reasons.append("legal_reviewer_missing")
    checks = entry.get("checks")
    if not isinstance(checks, dict):
        reasons.append("legal_checks_missing")
    else:
        for name in sorted(REQUIRED_LEGAL_CHECKS):
            item = checks.get(name)
            if not isinstance(item, dict) or item.get("reviewed") is not True:
                reasons.append(f"legal_check_missing:{name}")
            elif not item.get("source_urls") or not all(
                    _valid_https(url) for url in item["source_urls"]):
                reasons.append(f"legal_source_missing:{name}")
    return not reasons, reasons


def intake_validation(parcel: dict[str, Any]) -> dict[str, Any]:
    """Validate the standardized discovery record before scoring it."""
    reasons: list[str] = []
    for field in ("county_assessor_url", "county_recorder_url"):
        if not _valid_https(parcel.get(field)):
            reasons.append(f"{field}_invalid")
    try:
        confidence = finite_number(parcel.get("owner_identity_confidence"),
                                   "owner_identity_confidence", maximum=1)
        if confidence < 0.7:
            reasons.append("owner_identity_confidence_too_low")
    except ValueError as exc:
        confidence = 0.0
        reasons.append(str(exc))
    for field, minimum in (("asking_price", 1), ("acreage", 0.01),
                           ("days_listed", 0)):
        try:
            finite_number(parcel.get(field), field, minimum=minimum)
        except ValueError as exc:
            reasons.append(str(exc))
    return {"owner_identity_confidence": confidence,
            "hard_blocks": sorted(set(reasons))}


def normalize_parcel_id(value: Any) -> str:
    normalized = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    if len(normalized) < 3:
        raise ValueError("parcel_id_invalid")
    return normalized


def parcel_key(parcel: dict[str, Any]) -> str:
    jurisdiction = str(parcel.get("jurisdiction") or "").strip().upper()
    county = re.sub(r"\s+", " ", str(parcel.get("county") or "").strip().upper())
    if not jurisdiction or not county:
        raise ValueError("jurisdiction_and_county_required")
    return f"{jurisdiction}|{county}|{normalize_parcel_id(parcel.get('parcel_id'))}"


def source_quality(parcel: dict[str, Any], now: datetime,
                   stale_days: int) -> tuple[float, list[str], datetime | None]:
    source = parcel.get("source")
    reasons: list[str] = []
    if not isinstance(source, dict):
        return 0.0, ["source_required"], None
    if source.get("type") not in ALLOWED_SOURCE_TYPES:
        reasons.append("source_type_not_authorized")
    for field in ("record_url", "terms_url"):
        if not _valid_https(source.get(field)):
            reasons.append(f"source_{field}_invalid")
    if source.get("collection_authorized") is not True:
        reasons.append("source_collection_not_authorized")
    if source.get("terms_reviewed") is not True:
        reasons.append("source_terms_not_reviewed")
    if source.get("robots_respected") is not True:
        reasons.append("source_robots_not_respected")
    try:
        observed = parse_time(source.get("observed_at"), "source_observed_at")
        if observed > now + timedelta(minutes=5):
            reasons.append("source_observed_in_future")
        elif now - observed > timedelta(days=stale_days):
            reasons.append("source_stale")
    except ValueError as exc:
        observed = None
        reasons.append(str(exc))
    quality = max(0.0, 1.0 - 0.14 * len(set(reasons)))
    return round(quality, 3), sorted(set(reasons)), observed


def deduplicate(parcels: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep the freshest source record for each jurisdiction/county/parcel ID."""
    selected: dict[str, tuple[datetime, int, dict[str, Any]]] = {}
    duplicates: list[dict[str, Any]] = []
    for index, parcel in enumerate(parcels):
        try:
            key = parcel_key(parcel)
            observed = parse_time((parcel.get("source") or {}).get("observed_at"), "source_observed_at")
        except (AttributeError, ValueError):
            key = f"invalid:{index}"
            observed = datetime.min.replace(tzinfo=timezone.utc)
        prior = selected.get(key)
        if prior is None or observed > prior[0]:
            if prior is not None:
                duplicates.append({"parcel_key": key, "discarded_index": prior[1],
                                   "reason": "duplicate_older_source"})
            selected[key] = (observed, index, parcel)
        else:
            duplicates.append({"parcel_key": key, "discarded_index": index,
                               "reason": "duplicate_older_or_equal_source"})
    kept = [item[2] for item in sorted(selected.values(), key=lambda item: item[1])]
    return kept, duplicates


def _closed_comp(comp: dict[str, Any], now: datetime) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if comp.get("status") != "closed_sale":
        reasons.append("not_closed_sale")
    if comp.get("verified") is not True:
        reasons.append("comp_not_verified")
    if not _valid_https(comp.get("source_url")):
        reasons.append("comp_source_invalid")
    try:
        sale_date = parse_time(comp.get("sale_date"), "comp_sale_date")
        if sale_date > now + timedelta(minutes=5):
            reasons.append("comp_sale_date_future")
        elif now - sale_date > timedelta(days=730):
            reasons.append("comp_sale_too_old")
    except ValueError as exc:
        reasons.append(str(exc))
    try:
        finite_number(comp.get("sale_price"), "comp_sale_price", minimum=1)
        finite_number(comp.get("acreage"), "comp_acreage", minimum=0.01)
        finite_number(comp.get("distance_miles"), "comp_distance_miles")
    except ValueError as exc:
        reasons.append(str(exc))
    return not reasons, sorted(set(reasons))


def comp_analysis(parcel: dict[str, Any], now: datetime) -> dict[str, Any]:
    try:
        acreage = finite_number(parcel.get("acreage"), "acreage", minimum=0.01)
    except ValueError as exc:
        return {"confidence": 0.0, "supported_sale_price": 0,
                "valid_comp_count": 0, "reason_codes": [str(exc)]}
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, comp in enumerate(parcel.get("comps") or []):
        if not isinstance(comp, dict):
            rejected.append({"index": index, "reasons": ["comp_invalid"]})
            continue
        ok, reasons = _closed_comp(comp, now)
        (valid if ok else rejected).append(comp if ok else {"index": index, "reasons": reasons})
    if not valid:
        return {"confidence": 0.0, "supported_sale_price": 0,
                "valid_comp_count": 0, "rejected_comps": rejected,
                "reason_codes": ["no_verified_closed_comps"]}
    ppa = [finite_number(item["sale_price"], "comp_sale_price", minimum=1) /
           finite_number(item["acreage"], "comp_acreage", minimum=0.01)
           for item in valid]
    median_ppa = statistics.median(ppa)
    mad = statistics.median(abs(value - median_ppa) for value in ppa)
    filtered = [(item, value) for item, value in zip(valid, ppa)
                if not mad or abs(value - median_ppa) <= 3.5 * mad]
    outliers = len(valid) - len(filtered)
    if not filtered:
        return {"confidence": 0.0, "supported_sale_price": 0,
                "valid_comp_count": 0, "rejected_comps": rejected,
                "reason_codes": ["all_comps_outliers"]}
    values = sorted(value for _, value in filtered)
    lower_index = max(0, math.ceil(len(values) * 0.35) - 1)
    supported_ppa = min(statistics.median(values), values[lower_index])
    supported_sale_price = round(supported_ppa * acreage)
    count_score = min(1.0, len(filtered) / 4)
    distance_score = sum(max(0.0, 1 - finite_number(item["distance_miles"], "distance_miles") / 50)
                         for item, _ in filtered) / len(filtered)
    acreage_score = sum(min(acreage, finite_number(item["acreage"], "comp_acreage", minimum=0.01)) /
                        max(acreage, finite_number(item["acreage"], "comp_acreage", minimum=0.01))
                        for item, _ in filtered) / len(filtered)
    confidence = round(0.5 * count_score + 0.25 * distance_score + 0.25 * acreage_score, 3)
    reasons = (["too_few_verified_comps"] if len(filtered) < 3 else []) + (
        ["comp_outliers_excluded"] if outliers else [])
    return {"confidence": confidence, "supported_sale_price": supported_sale_price,
            "supported_price_per_acre": round(supported_ppa, 2),
            "valid_comp_count": len(filtered), "outlier_count": outliers,
            "rejected_comps": rejected, "reason_codes": reasons}


def due_diligence(parcel: dict[str, Any]) -> dict[str, Any]:
    diligence = parcel.get("due_diligence")
    if not isinstance(diligence, dict):
        return {"completeness": 0.0, "hard_blocks": ["due_diligence_missing"],
                "reason_codes": ["due_diligence_missing"]}
    missing = sorted(name for name in REQUIRED_DUE_DILIGENCE if name not in diligence)
    blocks: list[str] = []
    evidence_urls = diligence.get("evidence_urls")
    if not isinstance(evidence_urls, list) or not evidence_urls or not all(
            _valid_https(url) for url in evidence_urls):
        blocks.append("due_diligence_sources_missing")
    if missing:
        blocks.append("due_diligence_incomplete")
    if diligence.get("legal_road_access") is not True:
        blocks.append("no_verified_legal_road_access")
    if not _valid_https(diligence.get("title_evidence_url")):
        blocks.append("title_evidence_missing")
    title_flags = diligence.get("title_flags")
    if not isinstance(title_flags, list):
        blocks.append("title_flags_unreviewed")
    elif title_flags:
        blocks.append("unresolved_title_flags")
    for name in ("unpaid_taxes", "liens"):
        if diligence.get(name) in (None, "unknown"):
            blocks.append(f"{name}_unknown")
    completeness = (len(REQUIRED_DUE_DILIGENCE) - len(missing)) / len(REQUIRED_DUE_DILIGENCE)
    return {"completeness": round(max(0.0, completeness), 3),
            "hard_blocks": sorted(set(blocks)), "reason_codes": missing}


def verified_buyer(parcel: dict[str, Any], now: datetime) -> tuple[bool, list[str]]:
    buyer = parcel.get("buyer_intent")
    if not isinstance(buyer, dict) or buyer.get("verified") is not True:
        return False, (["unsupported_government_buyer_claim"]
                       if parcel.get("government_buyer_claim") else ["verified_buyer_intent_missing"])
    reasons: list[str] = []
    if parcel.get("government_buyer_claim") and buyer.get("kind") != "government":
        reasons.append("unsupported_government_buyer_claim")
    if not _valid_https(buyer.get("evidence_url")):
        reasons.append("buyer_evidence_invalid")
    try:
        verified_at = parse_time(buyer.get("verified_at"), "buyer_verified_at")
        if verified_at > now + timedelta(minutes=5) or now - verified_at > timedelta(days=30):
            reasons.append("buyer_evidence_not_fresh")
    except ValueError as exc:
        reasons.append(str(exc))
    if buyer.get("kind") == "government":
        if not buyer.get("solicitation_id") or not _valid_https(buyer.get("procurement_url")):
            reasons.append("unsupported_government_buyer_claim")
    return not reasons, sorted(set(reasons))


def cost_analysis(parcel: dict[str, Any], supported_sale_price: float) -> dict[str, Any]:
    purchase = parcel.get("proposed_purchase_price", parcel.get("asking_price"))
    try:
        purchase_price = finite_number(purchase, "purchase_price", minimum=1)
    except ValueError as exc:
        return {"gross_spread": 0, "net_potential": 0, "total_costs": 0,
                "purchase_price": 0, "reason_codes": [str(exc)]}
    required = ("closing", "due_diligence", "legal_assignment", "carrying_marketing",
                "taxes_liens", "uncertainty_reserve")
    costs = parcel.get("costs")
    reasons: list[str] = []
    total = 0.0
    if not isinstance(costs, dict):
        reasons.append("costs_missing")
    else:
        for name in required:
            try:
                total += finite_number(costs.get(name), f"cost_{name}")
            except ValueError as exc:
                reasons.append(str(exc))
    gross = max(0.0, supported_sale_price - purchase_price)
    return {"purchase_price": round(purchase_price, 2), "gross_spread": round(gross, 2),
            "total_costs": round(total, 2),
            "net_potential": round(supported_sale_price - purchase_price - total, 2),
            "reason_codes": sorted(set(reasons))}


def evaluate(parcel: dict[str, Any], policy: dict[str, Any], *,
             now: datetime | None = None, stale_days: int = DEFAULT_STALE_DAYS) -> dict[str, Any]:
    current = _now(now)
    reasons: list[str] = []
    try:
        key = parcel_key(parcel)
    except ValueError as exc:
        key = "invalid:" + hashlib.sha256(json.dumps(parcel, sort_keys=True, default=str).encode()).hexdigest()[:16]
        reasons.append(str(exc))
    jurisdiction = str(parcel.get("jurisdiction") or "").strip().upper()
    _, legal_reasons = jurisdiction_gate(policy, jurisdiction, current)
    intake = intake_validation(parcel)
    source_score, source_reasons, observed = source_quality(parcel, current, stale_days)
    comps = comp_analysis(parcel, current)
    diligence = due_diligence(parcel)
    buyer_ok, buyer_reasons = verified_buyer(parcel, current)
    economics = cost_analysis(parcel, comps["supported_sale_price"])
    reasons.extend(legal_reasons + intake["hard_blocks"] + source_reasons + comps["reason_codes"] +
                   diligence["reason_codes"] + diligence["hard_blocks"] +
                   buyer_reasons + economics["reason_codes"])
    hard_blocks = set(legal_reasons + intake["hard_blocks"] + source_reasons +
                      diligence["hard_blocks"])
    if comps["valid_comp_count"] == 0:
        hard_blocks.add("no_verified_closed_comps")
    if economics["net_potential"] <= 0:
        hard_blocks.add("nonpositive_conservative_net")
    if parcel.get("government_buyer_claim") and not buyer_ok:
        hard_blocks.add("unsupported_government_buyer_claim")
    margin_ratio = (max(0.0, economics["net_potential"] / comps["supported_sale_price"])
                    if comps["supported_sale_price"] else 0.0)
    score = round(100 * (0.35 * comps["confidence"] +
                         0.25 * diligence["completeness"] +
                         0.25 * min(1.0, margin_ratio / 0.25) +
                         0.15 * source_score), 2)
    if hard_blocks:
        score = 0.0
    uncertainty = "high" if hard_blocks or comps["confidence"] < 0.5 else (
        "medium" if comps["confidence"] < 0.75 or diligence["completeness"] < 1 else "low")
    contract_ok = _contract_verified(parcel)
    settled_ok, _ = _settled_deal(parcel, current)
    stage = ("settled" if settled_ok else "contract" if contract_ok else
             "verified_buyer" if buyer_ok else
             "verified_comp" if comps["valid_comp_count"] else "discovered")
    return {"parcel_key": key,
            "source_observed_at": observed.isoformat() if observed else None,
            "eligible_for_research_digest": not hard_blocks,
            "score": score, "uncertainty": uncertainty, "stage": stage,
            "reason_codes": sorted(set(reasons) | hard_blocks),
            "hard_blocks": sorted(hard_blocks), "intake": intake,
            "comp_analysis": comps,
            "due_diligence": diligence, "economics": economics,
            "buyer_intent_verified": buyer_ok,
            "lifecycle": {"discovered": True,
                          "verified_comp": comps["valid_comp_count"] > 0,
                          "verified_buyer": buyer_ok,
                          "contract_externally_accepted": contract_ok,
                          "settled": settled_ok},
            "projected_value_is_revenue": False,
            "execution": {"mode": "research_only_dry_run", "outreach_allowed": False,
                          "advertising_rights_claimed": False,
                          "contract_or_signature_allowed": False,
                          "deposit_or_purchase_allowed": False}}


def _contract_verified(record: dict[str, Any]) -> bool:
    contract = record.get("contract")
    return (isinstance(contract, dict) and contract.get("externally_accepted") is True and
            contract.get("reviewed_for_jurisdiction") is True and
            _valid_https(contract.get("evidence_url")) and
            bool(str(contract.get("provider_contract_id") or "").strip()))


def _settled_deal(record: dict[str, Any], now: datetime | None = None) -> tuple[bool, int]:
    settled = record.get("settled")
    if not isinstance(settled, dict):
        return False, 0
    try:
        amount = round(finite_number(settled.get("net_revenue_cents"), "net_revenue_cents"))
    except ValueError:
        return False, 0
    try:
        settled_at = parse_time(settled.get("settled_at"), "settled_at")
    except ValueError:
        return False, 0
    valid = (_contract_verified(record) and settled.get("verified") is True and
             bool(str(settled.get("provider_transaction_id") or "").strip()) and
             bool(str(settled.get("closing_provider") or "").strip()) and
             str(settled.get("currency") or "").upper() == "USD" and
             settled_at <= _now(now) + timedelta(minutes=5) and
             _valid_https(settled.get("evidence_url")))
    return valid, amount if valid else 0


def digest(parcels: list[dict[str, Any]], policy: dict[str, Any], *,
           now: datetime | None = None, stale_days: int = DEFAULT_STALE_DAYS) -> dict[str, Any]:
    if not isinstance(parcels, list):
        raise ValueError("parcels_must_be_list")
    current = _now(now)
    kept, duplicates = deduplicate(parcels)
    evaluated = [evaluate(parcel, policy, now=current, stale_days=stale_days) for parcel in kept]
    evaluated.sort(key=lambda item: (-item["score"], item["parcel_key"]))
    settled = [_settled_deal(parcel, current) for parcel in kept]
    return {"generated_at": current.isoformat(), "mode": "research_only_dry_run",
            "input_count": len(parcels), "deduplicated_count": len(kept),
            "duplicate_count": len(duplicates),
            "qualified_research_count": sum(item["eligible_for_research_digest"] for item in evaluated),
            "verified_settled_deals": sum(1 for verified, _ in settled if verified),
            "verified_revenue_cents": sum(amount for verified, amount in settled if verified),
            "projected_net_potential_cents": 0,
            "projection_policy": "projected spreads and asking/AI values never count as revenue",
            "guardrails": {"outreach": False, "advertising_property_rights": False,
                           "contracts_or_signatures": False, "deposits_or_purchases": False,
                           "paid_data_or_advertising": False,
                           "government_buyer_inference": False},
            "duplicates": duplicates, "opportunities": evaluated}


def main() -> int:
    parser = argparse.ArgumentParser(description="Produce a no-side-effect land research scorecard")
    parser.add_argument("input", nargs="?", help="JSON file; omit or use - for stdin")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    args = parser.parse_args()
    source = sys.stdin if not args.input or args.input == "-" else open(args.input, "r", encoding="utf-8")
    try:
        payload = json.load(source)
    finally:
        if source is not sys.stdin:
            source.close()
    parcels = payload.get("parcels") if isinstance(payload, dict) else payload
    print(json.dumps(digest(parcels, load_policy(args.policy),
                            stale_days=max(1, args.stale_days)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
