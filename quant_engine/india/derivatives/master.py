"""AMQUANT INDIA - Indian Derivatives (F&O) Instrument Master & Specifications.

Covers:
1. Futures & Options Contract Representation:
   - Index Futures (FUTIDX), Stock Futures (FUTSTK)
   - Index Options (OPTIDX), Stock Options (OPTSTK)
   - Standard NSE Contract Symbol convention
2. Historical Lot-Size Change Registry:
   - Accurately tracks SEBI & NSE lot size revisions across calendar regimes.
3. Expiry Calendar Engine:
   - Last-Thursday monthly expiries with holiday-aware rollbacks.
4. Contract Master Catalog.
"""

from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

ContractType = Literal["FUTIDX", "FUTSTK", "OPTIDX", "OPTSTK"]
OptionType = Literal["CE", "PE"]
Exchange = Literal["NSE", "BSE"]


@dataclass(frozen=True)
class DerivativesContract:
    symbol: str  # e.g., NIFTY24DEC25000CE or RELIANCE24DECFUT
    underlying_symbol: str  # e.g., NIFTY 50 or RELIANCE
    exchange: Exchange
    contract_type: ContractType
    expiry_date: str  # YYYY-MM-DD
    strike_price: float  # 0.0 for Futures
    option_type: OptionType | None  # 'CE' | 'PE' | None
    lot_size: int
    tick_size: float = 0.05
    listing_date: str = ""
    last_trading_date: str = ""
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------------
# Historical Lot Size Change Records (SEBI & Exchange Circulars)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class LotSizeSchedule:
    start_date: str
    end_date: str | None  # None indicates currently active
    lot_size: int


HISTORICAL_LOT_SIZES: dict[str, list[LotSizeSchedule]] = {
    "NIFTY 50": [
        LotSizeSchedule("2000-06-12", "2015-10-29", 50),
        LotSizeSchedule("2015-10-30", "2021-04-29", 75),
        LotSizeSchedule("2021-04-30", "2024-04-25", 50),
        LotSizeSchedule("2024-04-26", "2024-11-19", 25),
        LotSizeSchedule("2024-11-20", None, 75),  # SEBI Circular Nov 2024
    ],
    "NIFTY BANK": [
        LotSizeSchedule("2003-06-13", "2016-06-30", 30),
        LotSizeSchedule("2016-07-01", "2020-07-02", 20),
        LotSizeSchedule("2020-07-03", "2023-07-13", 25),
        LotSizeSchedule("2023-07-14", "2024-11-19", 15),
        LotSizeSchedule("2024-11-20", None, 30),
    ],
    "NIFTY FINANCIAL SERVICES": [
        LotSizeSchedule("2021-01-11", "2024-11-19", 40),
        LotSizeSchedule("2024-11-20", None, 65),
    ],
    "NIFTY MIDCAP SELECT": [
        LotSizeSchedule("2022-01-24", "2024-11-19", 75),
        LotSizeSchedule("2024-11-20", None, 120),
    ],
    "SENSEX": [
        LotSizeSchedule("2000-06-09", "2023-05-11", 15),
        LotSizeSchedule("2023-05-12", "2024-11-19", 10),
        LotSizeSchedule("2024-11-20", None, 20),
    ],
    "RELIANCE": [
        LotSizeSchedule("2017-09-08", "2021-04-29", 500),
        LotSizeSchedule("2021-04-30", None, 250),
    ],
    "TCS": [
        LotSizeSchedule("2018-06-01", "2021-04-29", 300),
        LotSizeSchedule("2021-04-30", None, 175),
    ],
    "INFY": [
        LotSizeSchedule("2018-09-07", "2021-04-29", 600),
        LotSizeSchedule("2021-04-30", None, 400),
    ],
    "HDFCBANK": [
        LotSizeSchedule("2019-09-20", None, 550),
    ],
    "ICICIBANK": [
        LotSizeSchedule("2021-04-30", None, 700),
    ],
    "SBIN": [
        LotSizeSchedule("2021-04-30", None, 1500),
    ],
    "TATAMOTORS": [
        LotSizeSchedule("2021-04-30", None, 1425),
    ],
}


def _normalize_underlying_symbol(underlying: str) -> str:
    clean = underlying.strip().upper()
    if clean in ("NIFTY", "NIFTY50", "NIFTY 50", "^NSEI"):
        return "NIFTY 50"
    if clean in ("BANKNIFTY", "NIFTYBANK", "NIFTY BANK", "BANK NIFTY", "^NSEBANK"):
        return "NIFTY BANK"
    return clean


def get_historical_lot_size(underlying: str, as_of_date: str | date | None = None) -> int:
    """Retrieve the authentic lot size for an Indian underlying on a specific historical date."""
    clean_sym = _normalize_underlying_symbol(underlying)
    schedules = HISTORICAL_LOT_SIZES.get(clean_sym)
    if not schedules:
        # Default single stock lot size estimate if unlisted in table
        return 250

    if as_of_date is None:
        target_str = datetime.now().strftime("%Y-%m-%d")
    elif isinstance(as_of_date, date):
        target_str = as_of_date.strftime("%Y-%m-%d")
    else:
        target_str = str(as_of_date)[:10]

    for sched in schedules:
        if sched.start_date <= target_str:
            if sched.end_date is None or target_str <= sched.end_date:
                return sched.lot_size

    # Fallback to last known schedule
    return schedules[-1].lot_size


def get_lot_size_history(underlying: str) -> list[dict[str, Any]]:
    """Return all historical lot size revisions for an underlying."""
    clean_sym = _normalize_underlying_symbol(underlying)
    schedules = HISTORICAL_LOT_SIZES.get(clean_sym, [])
    return [
        {
            "underlying": clean_sym,
            "start_date": s.start_date,
            "end_date": s.end_date or "Present",
            "lot_size": s.lot_size,
        }
        for s in schedules
    ]


# ----------------------------------------------------------------------
# Expiry Calendar Engine
# ----------------------------------------------------------------------
def get_monthly_expiry_date(year: int, month: int, holidays: set[str] | None = None) -> str:
    """Calculate the NSE monthly contract expiry date (Last Thursday of the month).

    If the last Thursday is an exchange holiday, it rolls back to Wednesday.
    """
    from quant_engine.india.intraday import STANDARD_INDIAN_HOLIDAYS_2024_2026
    hols = holidays or STANDARD_INDIAN_HOLIDAYS_2024_2026

    # Find the last day of the month
    _, last_day = calendar.monthrange(year, month)
    dt = date(year, month, last_day)

    # Roll back to Thursday (weekday 3: Monday=0, Thursday=3)
    while dt.weekday() != 3:
        dt -= timedelta(days=1)

    # If Thursday is a trading holiday, roll back to Wednesday (or earlier)
    while dt.strftime("%Y-%m-%d") in hols:
        dt -= timedelta(days=1)

    return dt.strftime("%Y-%m-%d")


def build_contract_symbol(
    underlying: str,
    expiry_date: str,
    contract_type: ContractType,
    strike_price: float = 0.0,
    option_type: OptionType | None = None,
) -> str:
    """Format contract symbol conforming to NSE standard symbol format.

    Examples:
        NIFTY + 2024-12-26 + FUTIDX -> NIFTY24DECFUT
        NIFTY + 2024-12-26 + OPTIDX + 25000 + CE -> NIFTY24DEC25000CE
        RELIANCE + 2024-12-26 + FUTSTK -> RELIANCE24DECFUT
        RELIANCE + 2024-12-26 + OPTSTK + 2600 + PE -> RELIANCE24DEC2600PE
    """
    clean_underlying = underlying.strip().upper().replace(" ", "").replace("^NSEI", "NIFTY")
    if "NIFTY50" in clean_underlying:
        clean_underlying = "NIFTY"
    elif "NIFTYBANK" in clean_underlying:
        clean_underlying = "BANKNIFTY"

    dt = datetime.strptime(expiry_date[:10], "%Y-%m-%d")
    yr_str = dt.strftime("%y")
    month_str = dt.strftime("%b").upper()

    if contract_type in ("FUTIDX", "FUTSTK"):
        return f"{clean_underlying}{yr_str}{month_str}FUT"

    strike_int = int(round(strike_price))
    opt_str = option_type or "CE"
    return f"{clean_underlying}{yr_str}{month_str}{strike_int}{opt_str}"


def generate_contract_master_catalog(
    underlyings: list[str] | None = None,
    year: int = 2024,
) -> list[DerivativesContract]:
    """Generate contract master catalog across near, mid, and far month cycles with active strikes."""
    targets = underlyings or ["NIFTY 50", "NIFTY BANK", "RELIANCE", "TCS", "INFY", "HDFCBANK"]
    catalog: list[DerivativesContract] = []

    # Strike steps for active underlyings
    strike_configs: dict[str, tuple[float, float, int]] = {
        "NIFTY 50": (24500.0, 50.0, 15),       # Base 24500, step 50, 15 strikes each side
        "NIFTY BANK": (52000.0, 100.0, 15),
        "RELIANCE": (2500.0, 20.0, 10),
        "TCS": (4100.0, 50.0, 10),
        "INFY": (1850.0, 20.0, 10),
        "HDFCBANK": (1750.0, 20.0, 10),
    }

    for und in targets:
        lot_sz = get_historical_lot_size(und)
        is_index = "NIFTY" in und or "SENSEX" in und
        fut_type: ContractType = "FUTIDX" if is_index else "FUTSTK"
        opt_type: ContractType = "OPTIDX" if is_index else "OPTSTK"

        # Generate 3 monthly cycles: near, next, far
        for month_offset in range(10, 13):  # Oct, Nov, Dec 2024
            exp_date = get_monthly_expiry_date(year, month_offset)

            # 1. Futures Contract
            fut_sym = build_contract_symbol(und, exp_date, fut_type)
            catalog.append(
                DerivativesContract(
                    symbol=fut_sym,
                    underlying_symbol=und,
                    exchange="NSE",
                    contract_type=fut_type,
                    expiry_date=exp_date,
                    strike_price=0.0,
                    option_type=None,
                    lot_size=lot_sz,
                    listing_date=f"{year}-01-01",
                    last_trading_date=exp_date,
                    is_active=True,
                )
            )

            # 2. Options Contracts across strike ladder
            base_p, step, n_steps = strike_configs.get(und, (1000.0, 50.0, 5))
            for i in range(-n_steps, n_steps + 1):
                strike = base_p + (i * step)
                if strike <= 0:
                    continue

                for kind in ("CE", "PE"):
                    opt_sym = build_contract_symbol(und, exp_date, opt_type, strike, kind)  # type: ignore
                    catalog.append(
                        DerivativesContract(
                            symbol=opt_sym,
                            underlying_symbol=und,
                            exchange="NSE",
                            contract_type=opt_type,
                            expiry_date=exp_date,
                            strike_price=strike,
                            option_type=kind,  # type: ignore
                            lot_size=lot_sz,
                            listing_date=f"{year}-01-01",
                            last_trading_date=exp_date,
                            is_active=True,
                        )
                    )

    return catalog

