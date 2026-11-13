"""Conservative REO screening. Research only; never an appraisal or offer authorization.

No network, scraping, messaging, contracting, or inferred proof of funds.
Dollar inputs are USD. All money calculations use Decimal.
"""
from decimal import Decimal, InvalidOperation
from typing import Mapping


def amount(value, name):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{name} must be a valid USD amount") from None
    if not number.is_finite() or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def screen_reo(candidate: Mapping) -> dict:
    """Returns a research-only screening result from caller-supplied verified inputs.

    Required: address, source_url, as_of, listing_price, days_on_market,
    price_cuts, arv_low, arv_high, repairs_low, repairs_high,
    holding_closing_costs, desired_fee.
    Missing inputs fail closed rather than being made up.
    """
    fields = ("address", "source_url", "as_of", "listing_price",
              "days_on_market", "price_cuts", "arv_low", "arv_high",
              "repairs_low", "repairs_high", "holding_closing_costs",
              "desired_fee")
    missing = [field for field in fields if field not in candidate]
    if missing:
        raise ValueError(f"Missing required inputs: {', '.join(missing)}")
    for field in ("address", "source_url", "as_of"):
        if not isinstance(candidate[field], str) or not candidate[field].strip():
            raise ValueError(f"{field} must be a nonempty source-backed string")
    if not candidate["source_url"].startswith("https://"):
        raise ValueError("source_url must be HTTPS")
    for field in ("days_on_market", "price_cuts"):
        value = candidate[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} must be a nonnegative integer")
    amounts = {key: amount(candidate[key], key) for key in (
        "listing_price", "arv_low", "arv_high", "repairs_low",
        "repairs_high", "holding_closing_costs", "desired_fee")}
    if amounts["arv_low"] > amounts["arv_high"]:
        raise ValueError("arv_low cannot exceed arv_high")
    if amounts["repairs_low"] > amounts["repairs_high"]:
        raise ValueError("repairs_low cannot exceed repairs_high")
    # Max offer is intentionally conservative: lowest ARV, highest repairs.
    # This is a heuristic, not a bank acceptance-price prediction.
    max_offer = (amounts["arv_low"] * Decimal("0.70")
                 - amounts["repairs_high"]
                 - amounts["holding_closing_costs"]
                 - amounts["desired_fee"])
    eligible_filter = candidate["days_on_market"] > 90 or candidate["price_cuts"] >= 2
    return {
        "address": candidate["address"],
        "source_url": candidate["source_url"],
        "as_of": candidate["as_of"],
        "watchlist_filter": eligible_filter,
        "screen_status": "research_only" if eligible_filter else "not_prioritized",
        "max_offer_heuristic_usd": str(max(Decimal("0"), max_offer).quantize(Decimal("0.01"))),
        "potential_spread_before_other_unknowns_usd": str(
            (amounts["arv_low"] - amounts["listing_price"] -
             amounts["repairs_high"] - amounts["holding_closing_costs"]).quantize(Decimal("0.01"))),
        "cautions": [
            "Not an appraisal or bank acceptance prediction",
            "No right to assign or advertise property has been established",
            "Verify sold comparables, inspection, title, liens, occupancy and local regulations",
            "Verify buyer funding, contract eligibility and all cost assumptions before an offer",
            "Do not claim proof of funds or conduct unauthorized brokerage activities",
        ],
        "automatic_offer_authorized": False,
        "automatic_outreach_authorized": False,
    }
