"""Research-only, compliance-gated vacant-land screening. No outreach or transactions."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable


@dataclass(frozen=True)
class Parcel:
    county: str
    parcel_id: str
    source_url: str
    asking_price: str
    supported_sale_price: str
    estimated_costs: str
    comparable_closed_sales: int
    legal_access_verified: bool
    title_reviewed: bool
    jurisdiction_cleared: bool
    verified_end_buyer: bool = False
    government_buyer_claim: bool = False


def _money(value: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid money amount") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("money amounts must be finite and nonnegative")
    return result


def screen(parcel: Parcel) -> dict:
    """Return a research scorecard, never a transaction authorization."""
    if not parcel.county.strip() or not parcel.parcel_id.strip() or not parcel.source_url.startswith(("https://", "http://")):
        raise ValueError("parcel identity and source URL required")
    if parcel.comparable_closed_sales < 0:
        raise ValueError("comparable count cannot be negative")
    asking = _money(parcel.asking_price)
    supported = _money(parcel.supported_sale_price)
    costs = _money(parcel.estimated_costs)
    net = supported - asking - costs
    blockers = []
    if not parcel.jurisdiction_cleared:
        blockers.append("jurisdiction_not_cleared")
    if not parcel.legal_access_verified:
        blockers.append("legal_access_unverified")
    if not parcel.title_reviewed:
        blockers.append("title_not_reviewed")
    if parcel.comparable_closed_sales < 3:
        blockers.append("insufficient_closed_comps")
    if not parcel.verified_end_buyer:
        blockers.append("buyer_not_verified")
    if parcel.government_buyer_claim and not parcel.verified_end_buyer:
        blockers.append("unsupported_government_buyer_claim")
    if net <= 0:
        blockers.append("nonpositive_estimated_margin")
    return {
        "key": f"{parcel.county.strip().casefold()}:{parcel.parcel_id.strip().casefold()}",
        "source_url": parcel.source_url,
        "gross_spread": str(supported - asking),
        "estimated_net": str(net),
        "comps": parcel.comparable_closed_sales,
        "confidence": "low" if blockers else "moderate",
        "status": "research_only" if blockers else "qualified_for_human_review",
        "blockers": blockers,
        "outreach_authorized": False,
        "transaction_authorized": False,
        "verified_revenue": "0",
    }


def screen_unique(parcels: Iterable[Parcel]) -> list[dict]:
    """Deduplicate stable county/parcel identifiers without contacting anyone."""
    results, seen = [], set()
    for parcel in parcels:
        result = screen(parcel)
        if result["key"] not in seen:
            seen.add(result["key"])
            results.append(result)
    return results
