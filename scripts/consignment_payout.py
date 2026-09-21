from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


MONEY = Decimal("0.01")


class PayoutStatus(str, Enum):
    PENDING = "pending"
    ELIGIBLE = "eligible"
    HELD = "held"
    REVERSED = "reversed"


def _money(value: Decimal | str | int) -> Decimal:
    amount = Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    if amount < 0:
        raise ValueError("amounts must be non-negative")
    return amount


@dataclass(frozen=True)
class PayoutInput:
    sold_at: date
    gross_sale: Decimal
    split_rate: Decimal
    marketplace_fees: Decimal = Decimal("0")
    approved_ad_fees: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")
    refund_amount: Decimal = Decimal("0")
    return_window_days: int = 30
    manual_hold: bool = False


@dataclass(frozen=True)
class PayoutResult:
    clears_at: date
    net_before_split: Decimal
    consignor_amount: Decimal
    status: PayoutStatus


def calculate_payout(data: PayoutInput, *, as_of: date) -> PayoutResult:
    """Calculate a review-ready payout without initiating any financial action."""
    gross = _money(data.gross_sale)
    marketplace_fees = _money(data.marketplace_fees)
    approved_ad_fees = _money(data.approved_ad_fees)
    other_deductions = _money(data.other_deductions)
    refund = _money(data.refund_amount)
    non_refund_deductions = marketplace_fees + approved_ad_fees + other_deductions
    fees = non_refund_deductions + refund
    split_rate = Decimal(str(data.split_rate))
    if not Decimal("0") <= split_rate <= Decimal("1"):
        raise ValueError("split_rate must be between 0 and 1")
    if data.return_window_days < 0:
        raise ValueError("return_window_days must be non-negative")

    net = max(Decimal("0"), gross - fees).quantize(MONEY)
    consignor_amount = (net * split_rate).quantize(MONEY, rounding=ROUND_HALF_UP)
    clears_at = data.sold_at + timedelta(days=data.return_window_days)

    inconsistent_deductions = non_refund_deductions > gross or refund > gross
    partial_refund = Decimal("0") < refund < gross
    full_refund = refund == gross and gross > 0

    if inconsistent_deductions or partial_refund:
        # Ambiguous source records must be reviewed rather than silently becoming
        # payable (or being presented as a complete reversal).
        status = PayoutStatus.HELD
    elif full_refund:
        status = PayoutStatus.REVERSED
    elif data.manual_hold:
        status = PayoutStatus.HELD
    elif as_of < clears_at:
        status = PayoutStatus.PENDING
    else:
        status = PayoutStatus.ELIGIBLE

    return PayoutResult(
        clears_at=clears_at,
        net_before_split=net,
        consignor_amount=consignor_amount,
        status=status,
    )
