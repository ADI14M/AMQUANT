"""Indian Financial Markets Transaction Cost & Statutory Taxes Engine.

Implements statutory Indian taxes and trading charges:
- Brokerage (Discount broker model: flat ₹20 or 0.03%)
- Securities Transaction Tax (STT) (Delivery: 0.1% buy & sell; Intraday: 0.025% sell)
- Exchange Turnover Fees (NSE: 0.00297%, BSE: 0.00375%)
- GST (18% on Brokerage + Exchange Fees + SEBI charges)
- SEBI Turnover Charges (₹10 / Crore = 0.0001%)
- Stamp Duty (0.015% on Buy for equity delivery)
- Empirical Market Impact / Slippage model
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

TradeSide = Literal["BUY", "SELL"]
TradeSegment = Literal["DELIVERY", "INTRADAY", "FUTURES", "OPTIONS"]


@dataclass(frozen=True)
class IndianCostBreakdown:
    gross_value: float
    side: TradeSide
    segment: TradeSegment
    brokerage: float
    stt: float
    exchange_charges: float
    sebi_charges: float
    stamp_duty: float
    gst: float
    slippage: float
    total_friction: float
    net_value: float
    effective_friction_bps: float

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


def calculate_indian_cost(
    price: float,
    quantity: int,
    side: TradeSide = "BUY",
    segment: TradeSegment = "DELIVERY",
    exchange: str = "NSE",
    base_slippage_bps: float = 3.0,
    brokerage_rate: float = 0.0003,  # 0.03% capped at ₹20
    brokerage_cap: float = 20.0,
) -> IndianCostBreakdown:
    """Calculate accurate Indian trading costs for an order execution."""
    if price <= 0:
        raise ValueError("Price must be strictly positive.")
    if quantity <= 0:
        raise ValueError("Quantity must be strictly positive.")

    gross_value = float(price * quantity)

    # 1. Brokerage
    brokerage = min(gross_value * brokerage_rate, brokerage_cap)

    # 2. Securities Transaction Tax (STT)
    if segment == "DELIVERY":
        # 0.1% on both Buy and Sell
        stt = gross_value * 0.001
    elif segment == "INTRADAY":
        # 0.025% on Sell only
        stt = gross_value * 0.00025 if side == "SELL" else 0.0
    elif segment == "FUTURES":
        # 0.02% on Sell only
        stt = gross_value * 0.0002 if side == "SELL" else 0.0
    elif segment == "OPTIONS":
        # 0.125% on Sell of premium
        stt = gross_value * 0.00125 if side == "SELL" else 0.0
    else:
        stt = 0.0

    # 3. Exchange Turnover Charges
    # NSE cash: 0.00297%, BSE cash: 0.00375%
    txn_rate = 0.0000375 if exchange.upper() == "BSE" else 0.0000297
    exchange_charges = gross_value * txn_rate

    # 4. SEBI Turnover Fees (₹10 / Crore = 0.000001 = 0.0001%)
    sebi_charges = gross_value * 0.000001

    # 5. Stamp Duty (State Stamp Act / Indian Stamp rules)
    # Delivery: 0.015% on Buy only. Intraday: 0.003% on Buy only.
    if side == "BUY":
        if segment == "DELIVERY":
            stamp_duty = gross_value * 0.00015
        elif segment == "INTRADAY":
            stamp_duty = gross_value * 0.00003
        else:
            stamp_duty = gross_value * 0.00002
    else:
        stamp_duty = 0.0

    # 6. GST (18% on Brokerage + Exchange Charges + SEBI charges)
    gst = 0.18 * (brokerage + exchange_charges + sebi_charges)

    # 7. Slippage / Market Impact
    slippage = gross_value * (base_slippage_bps / 10000.0)

    # Total Friction
    total_friction = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + slippage

    if side == "BUY":
        net_value = gross_value + total_friction
    else:
        net_value = max(0.0, gross_value - total_friction)

    effective_friction_bps = (total_friction / gross_value) * 10000.0 if gross_value > 0 else 0.0

    return IndianCostBreakdown(
        gross_value=round(gross_value, 2),
        side=side,
        segment=segment,
        brokerage=round(brokerage, 2),
        stt=round(stt, 2),
        exchange_charges=round(exchange_charges, 2),
        sebi_charges=round(sebi_charges, 4),
        stamp_duty=round(stamp_duty, 2),
        gst=round(gst, 2),
        slippage=round(slippage, 2),
        total_friction=round(total_friction, 2),
        net_value=round(net_value, 2),
        effective_friction_bps=round(effective_friction_bps, 2),
    )

