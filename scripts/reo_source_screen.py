#!/usr/bin/env python3
"""Fail-closed, offline REO research screening from manually verified public evidence.

No scraping, contacts, offers, automated brokerage or provider write actions.
Outputs are research flags, never appraisals, price predictions or revenue.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal, InvalidOperation, Overflow
from urllib.parse import urlparse


def dated(value: str, cutoff: date) -> date | None:
    try:
        d = date.fromisoformat(value)
        return d if d <= cutoff else None
    except (ValueError, TypeError):
        return None


def recent_check(value: object, cutoff: date, max_age_days: int = 7) -> bool:
    """A historic snapshot is not evidence of currently active/eligible inventory."""
    checked = dated(value, cutoff)
    return checked is not None and (cutoff - checked).days <= max_age_days


def source_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    p = urlparse(value)
    return p.scheme == "https" and bool(p.hostname) and '.' in p.hostname and not p.username


def amount(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and n >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def signed_amount(value: object) -> Decimal | None:
    """Signed adjustments are separate from nonnegative sale prices/costs."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def underwrite(item: dict, cutoff: date) -> dict:
    """Compute only a *scenario*, gated by sourced comps, costs and repair quotes."""
    x = item.get("underwriting")
    if not isinstance(x, dict):
        return {"ready": False, "reasons": ["underwriting_not_supplied"], "scenario_max_offer": None}
    reasons = []
    comps = x.get("closed_comps")
    if not isinstance(comps, list) or len(comps) < 3:
        reasons.append("at_least_three_sourced_closed_comps_required")
    else:
        comp_urls, comp_properties, adjusted_sales = [], [], []
        for c in comps:
            if not isinstance(c, dict):
                reasons.append("invalid_closed_comp_evidence")
                break
            address = c.get("property_address")
            closed_on = dated(c.get("closed_on"), cutoff)
            sold = amount(c.get("sold_price"))
            adjustment = signed_amount(c.get("arv_adjustment", 0))
            if (not source_url(c.get("source_url"))
                    or closed_on is None or sold is None or adjustment is None
                    or not isinstance(address, str) or not address.strip()):
                reasons.append("invalid_closed_comp_evidence")
                break
            if (cutoff - closed_on).days > 365:
                reasons.append("stale_closed_comp_evidence")
                break
            if adjustment != 0 and (not source_url(c.get("adjustment_source_url"))
                    or not isinstance(c.get("adjustment_reason"), str)
                    or not c["adjustment_reason"].strip()):
                reasons.append("comp_adjustment_evidence_missing")
                break
            try:
                adjusted = sold + adjustment
                if not adjusted.is_finite() or adjusted <= 0:
                    raise InvalidOperation("nonpositive adjusted sale")
            except (InvalidOperation, Overflow, OverflowError):
                reasons.append("invalid_adjusted_comp_price")
                break
            comp_urls.append(c["source_url"])
            comp_properties.append(" ".join(address.casefold().split()))
            adjusted_sales.append(adjusted)
        if len(comp_urls) == len(comps):
            if len(set(comp_urls)) != len(comp_urls):
                reasons.append("duplicate_closed_comp_source")
            if len(set(comp_properties)) != len(comp_properties):
                reasons.append("duplicate_closed_comp_property")
    arv = amount(x.get("arv"))
    if arv is None or not source_url(x.get("arv_source_url")):
        reasons.append("verified_arv_missing")
    # A supplied ARV must be reproducible from the median of at least three
    # distinct, recent closed sales after explicitly sourced adjustments.
    # This conservative scenario is not an appraisal of property comparability.
    if isinstance(comps, list) and len(comps) >= 3 and len(adjusted_sales) == len(comps):
        try:
            ordered = sorted(adjusted_sales)
            center = len(ordered) // 2
            derived_arv = (ordered[center] if len(ordered) % 2
                           else (ordered[center - 1] + ordered[center]) / Decimal("2"))
            if arv is not None and abs(derived_arv - arv) > Decimal("0.01"):
                reasons.append("arv_not_derived_from_adjusted_closed_comps")
        except (InvalidOperation, Overflow, OverflowError):
            reasons.append("invalid_adjusted_comp_price")
    fields = ("repairs_low", "repairs_high", "acquisition_cost", "selling_cost", "holding_cost", "uncertainty_reserve")
    numbers = {f: amount(x.get(f)) for f in fields}
    if any(v is None for v in numbers.values()):
        reasons.append("itemized_costs_missing")
    elif numbers["repairs_high"] < numbers["repairs_low"]:
        reasons.append("repair_range_inverted")
    if (not source_url(x.get("repair_quote_source_url"))
            or not recent_check(x.get("repair_quote_checked_on"), cutoff, max_age_days=30)):
        reasons.append("local_repair_quote_unverified_or_stale")
    if reasons:
        return {"ready": False, "reasons": reasons, "scenario_max_offer": None}
    try:
        cap = Decimal("0.70") * arv - numbers["repairs_high"] - numbers["acquisition_cost"] - numbers["selling_cost"] - numbers["holding_cost"] - numbers["uncertainty_reserve"]
        if not cap.is_finite():
            raise InvalidOperation("nonfinite scenario")
        scenario = str(max(Decimal("0"), cap).quantize(Decimal("0.01")))
    except (InvalidOperation, Overflow, OverflowError):
        return {"ready": False, "reasons": ["scenario_arithmetic_out_of_range"], "scenario_max_offer": None}
    return {"ready": True, "reasons": [], "scenario_max_offer": scenario, "label": "illustrative_70_percent_of_arv_screen_not_an_offer"}


def screen(payload: dict) -> dict:
    cutoff = date.fromisoformat(payload["as_of"])
    rows, seen = [], set()
    for item in payload.get("listings", []):
        if not isinstance(item, dict):
            raise ValueError("listing must be an object")
        link = item.get("official_listing_url")
        address = item.get("address")
        key = " ".join(address.casefold().split()) if isinstance(address, str) else ""
        issues = []
        if not key:
            issues.append("address_missing")
        if key in seen:
            issues.append("duplicate_listing")
        seen.add(key)
        if not source_url(link) or item.get("source_verified") is not True or not dated(item.get("checked_on"), cutoff):
            issues.append("official_source_not_verified")
        elif not recent_check(item.get("checked_on"), cutoff):
            issues.append("official_source_stale")
        if str(item.get("status", "")).lower() != "active":
            issues.append("not_confirmed_active")
        if item.get("investor_purchase_permitted") is False:
            issues.append("investor_purchase_prohibited")
        if item.get("investor_purchase_permitted") is not True:
            issues.append("investor_eligibility_not_confirmed")
        elif (not source_url(item.get("investor_eligibility_source_url"))
              or not recent_check(item.get("investor_eligibility_checked_on"), cutoff)):
            issues.append("investor_eligibility_evidence_missing_or_stale")
        current_price = amount(item.get("asking_price"))
        if current_price is None or current_price == 0:
            issues.append("current_ask_missing")
        listed_on = (dated(item.get("first_listed_on"), cutoff)
                     if item.get("first_listed_verified") is True and source_url(item.get("first_listed_source_url"))
                     else None)
        # Elapsed calendar days do not prove continuous on-market exposure.
        elapsed_days = (cutoff - listed_on).days if listed_on else None
        continuous_dom = (item.get("continuous_listing_verified") is True
                          and source_url(item.get("continuous_listing_source_url"))
                          and recent_check(item.get("continuous_listing_checked_on"), cutoff))
        days = elapsed_days if continuous_dom else None
        history = item.get("price_history") or []
        cuts = 0
        last = None
        valid_history = isinstance(history, list)
        for h in history if valid_history else []:
            # Operator attestation alone is insufficient: a dated, recently
            # reviewed *authoritative* source must support each historical event.
            # MLS-attributed third-party syndications are research leads, not
            # certified MLS/listing-agent reduction evidence.
            if (not isinstance(h, dict)
                    or not source_url(h.get("source_url"))
                    or not dated(h.get("dated_on"), cutoff)
                    or h.get("verified") is not True
                    or h.get("source_kind") not in ("official_mls_history", "seller_reo_portal_history", "listing_agent_written_history")
                    or not recent_check(h.get("source_checked_on"), cutoff)
                    or amount(h.get("price")) is None):
                valid_history = False
                break
            price = amount(h["price"])
            if last is not None and price < last:
                cuts += 1
            last = price
        dates = [h["dated_on"] for h in history] if valid_history else []
        if not valid_history or (history and (last != current_price or dates != sorted(dates) or len(dates) != len(set(dates)))):
            cuts = 0
            issues.append("price_history_not_verified")
        if not ((days is not None and days >= 90) or cuts >= 2):
            issues.append("no_verified_90_day_or_two_cut_trigger")
        # A 70%-of-ARV scenario is withheld unless the current listing, investor
        # status and qualifying research trigger all have valid evidence.
        # Underwrite's sourced comps alone cannot make a stale listing actionable.
        underwriting = (underwrite(item, cutoff) if not issues
                        else {"ready": False, "reasons": ["listing_research_preconditions_not_met"],
                              "scenario_max_offer": None})
        # No deal is ever auto-qualified; transaction/title/inspection and buyer gates are separate.
        rows.append({"address": item.get("address"), "official_listing_url": link, "asking_price": str(current_price) if current_price is not None else None,
            "calendar_days_since_first_listing": elapsed_days,
            "days_on_market_verified": days, "verified_price_cuts": cuts,
            "research_trigger_met": (days is not None and days >= 90) or cuts >= 2,
            "screen_status": "excluded" if "investor_purchase_prohibited" in issues else ("needs_evidence" if issues else "research_only_candidate"),
            "blocking_reasons": issues, "underwriting": underwriting,
            "external_action_allowed": False, "collected_revenue": "0"})
    return {"as_of": payload["as_of"], "mode": "offline_research_only", "screened": len(rows),
        "external_action_allowed": False, "collected_revenue": "0", "listings": rows}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="Manually checked JSON snapshots; no network calls")
    args = p.parse_args()
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(screen(data), indent=2))


if __name__ == "__main__":
    main()
