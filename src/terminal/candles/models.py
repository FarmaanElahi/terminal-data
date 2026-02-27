"""Pydantic schemas and helpers for the candles module.

Interval is a plain string that flows from TradingView all the way to Upstox.
The Upstox V3 API uses a {unit}/{num} path format, e.g.:
  /minutes/1   /minutes/15   /hours/1   /hours/4   /days/1   /weeks/1   /months/1

TradingView resolution strings:
  Pure integer  → minutes  (e.g. "1" = 1min, "15" = 15min, "60" = 60min, "240" = 4h)
  Suffix  D/d   → days     (e.g. "1D")
  Suffix  W/w   → weeks    (e.g. "1W")
  Suffix  M     → months   (e.g. "1M", "3M")   NOTE: uppercase M only — "m" is minutes

The backend does NOT hardcode a list of allowed intervals. Any value TV sends is
parsed dynamically and forwarded to Upstox. If Upstox rejects it, we log the error
and return [] so TradingView signals noData.
"""

import re
from pydantic import BaseModel

from terminal.models import TerminalBase


def tv_resolution_to_upstox(resolution: str) -> tuple[str, str] | None:
    """Convert a TradingView resolution string to Upstox V3 (unit, interval_num).

    TradingView format → Upstox V3:
      "1"    → ("minutes", "1")
      "5"    → ("minutes", "5")
      "60"   → ("hours",   "1")     # 60 min = 1 hour
      "120"  → ("hours",   "2")
      "1D"   → ("days",    "1")
      "2D"   → ("days",    "2")
      "1W"   → ("weeks",   "1")
      "1M"   → ("months",  "1")
      "3M"   → ("months",  "3")

    Returns None if the string cannot be parsed.
    """
    if not resolution:
        return None

    res = resolution.strip()

    # --- Suffix-based: days, weeks, months ---
    m = re.fullmatch(r"(\d+)([DdWwM])", res)
    if m:
        num = m.group(1)
        suffix = m.group(2)
        if suffix in ("D", "d"):
            return ("days", num)
        if suffix in ("W", "w"):
            return ("weeks", num)
        if suffix == "M":  # uppercase M → months
            return ("months", num)
        # lowercase m handled below as minutes

    # --- Just a letter (TV shorthand like "D", "W", "M") ---
    if res in ("D", "d"):
        return ("days", "1")
    if res in ("W", "w"):
        return ("weeks", "1")
    if res == "M":
        return ("months", "1")

    # --- Pure integer → minutes, auto-upgrade to hours if divisible ---
    if res.isdigit():
        minutes = int(res)
        if minutes >= 60 and minutes % 60 == 0:
            return ("hours", str(minutes // 60))
        return ("minutes", str(minutes))

    # --- Internal formats from our own code (1m, 5m, 1h, 1d, 1w, 1M) ---
    m2 = re.fullmatch(r"(\d+)([mhdwM])", res)
    if m2:
        num = m2.group(1)
        unit_char = m2.group(2)
        if unit_char == "m":
            return ("minutes", num)
        if unit_char == "h":
            return ("hours", num)
        if unit_char == "d":
            return ("days", num)
        if unit_char == "w":
            return ("weeks", num)
        if unit_char == "M":
            return ("months", num)

    return None


def is_intraday_unit(unit: str) -> bool:
    """Return True for units that support live intraday fetching (minutes, hours, or days)."""
    return unit in ("minutes", "hours", "days")


def upstox_chunk_days(unit: str) -> int:
    """Max days per single Upstox historical API request for a given unit.

    upstox enforces per-request limits (around 5000-10000 bars):
      minutes / hours → 7 days (safer for lower resolutions)
      days            → 365 days (1 year)
      weeks / months  → effectively unlimited
    """
    if unit in ("minutes", "hours"):
        return 7
    if unit == "days":
        return 3650  # 10 years
    return 3650  # weeks / months


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class Candle(BaseModel):
    """A single OHLCV candle."""

    timestamp: str  # ISO 8601 string from Upstox (e.g. "2025-01-02T09:15:00+05:30")
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: int = 0


class CandleResponse(TerminalBase):
    """API response for candle data."""

    ticker: str
    interval: str
    candles: list[Candle]
