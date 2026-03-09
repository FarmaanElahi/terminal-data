"""Drawing geometry resolver — converts stored price/time levels to trigger signals.

Supported drawing types:
  - trendline  – linear interpolation/extrapolation between two anchor points
  - hline      – fixed horizontal price level
  - rectangle  – box defined by (top, bottom, left, right)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def evaluate_drawing_condition(
    trigger_condition: dict,
    current_close: float,
    previous_close: float,
    current_timestamp: int,
) -> bool:
    """Evaluate a drawing-based alert condition.

    Parameters
    ----------
    trigger_condition : dict
        The ``trigger_condition`` JSONB from the Alert model.
    current_close : float
        The current bar's close price.
    previous_close : float
        The previous bar's close price (for cross detection).
    current_timestamp : int
        The current bar's timestamp in Unix seconds.

    Returns
    -------
    bool
        True if the drawing condition is met.
    """
    drawing_type = trigger_condition.get("drawing_type")
    trigger_when = trigger_condition.get("trigger_when", "")

    if drawing_type == "trendline":
        return _eval_trendline(trigger_condition, current_close, previous_close, current_timestamp)
    elif drawing_type == "hline":
        return _eval_hline(trigger_condition, current_close, previous_close)
    elif drawing_type == "rectangle":
        return _eval_rectangle(
            trigger_condition, current_close, previous_close, current_timestamp
        )
    else:
        logger.warning("Unknown drawing type: %s", drawing_type)
        return False


def _eval_trendline(
    cond: dict,
    current_close: float,
    previous_close: float,
    current_timestamp: int,
) -> bool:
    """Evaluate a trendline alert via linear interpolation.

    The trendline is defined by two anchor points. The price at the current
    timestamp is computed by linear interpolation (or extrapolation if
    the current time is outside the anchor range).
    """
    points = cond.get("points", [])
    if len(points) < 2:
        return False

    t1, p1 = points[0]["time"], points[0]["price"]
    t2, p2 = points[1]["time"], points[1]["price"]

    # Compute trendline price at current timestamp via linear interpolation
    dt = t2 - t1
    if dt == 0:
        # Degenerate trendline (both points at same time) — treat as hline at avg price
        trendline_price = (p1 + p2) / 2.0
        prev_trendline_price = trendline_price
    else:
        slope = (p2 - p1) / dt
        trendline_price = p1 + slope * (current_timestamp - t1)
        # Compute trendline price at previous timestamp for cross detection
        # Estimate previous timestamp as ~1 bar ago (86400s for daily)
        prev_timestamp = current_timestamp - 86400
        prev_trendline_price = p1 + slope * (prev_timestamp - t1)

    trigger_when = cond.get("trigger_when", "")
    return _check_cross(
        trigger_when, current_close, previous_close, trendline_price, prev_trendline_price
    )


def _eval_hline(
    cond: dict,
    current_close: float,
    previous_close: float,
) -> bool:
    """Evaluate a horizontal line alert."""
    price = cond.get("price", 0)
    trigger_when = cond.get("trigger_when", "")
    # For hline the reference price doesn't change
    return _check_cross(trigger_when, current_close, previous_close, price, price)


def _eval_rectangle(
    cond: dict,
    current_close: float,
    previous_close: float,
    current_timestamp: int,
) -> bool:
    """Evaluate a rectangle alert.

    Rectangle defined by (top, bottom, left, right).
    'enters' = price transitions from outside to inside the box.
    'exits' = price transitions from inside to outside.
    'enters_or_exits' = any transition across a boundary.
    """
    top = cond.get("top", 0)
    bottom = cond.get("bottom", 0)
    left = cond.get("left", 0)
    right = cond.get("right", 0)

    # Time check: only consider if current time is within the rectangle's time range
    # If outside the time range, the rectangle doesn't apply
    in_time_range = left <= current_timestamp <= right

    if not in_time_range:
        return False

    # Check if price is inside the rectangle
    currently_inside = bottom <= current_close <= top
    previously_inside = bottom <= previous_close <= top

    trigger_when = cond.get("trigger_when", "")

    if trigger_when == "enters":
        return currently_inside and not previously_inside
    elif trigger_when == "exits":
        return not currently_inside and previously_inside
    elif trigger_when == "enters_or_exits":
        return currently_inside != previously_inside
    else:
        return False


def _check_cross(
    trigger_when: str,
    current_price: float,
    previous_price: float,
    current_level: float,
    previous_level: float,
) -> bool:
    """Check if price has crossed a dynamic level.

    'crosses_above': previous was at/below the level, now above.
    'crosses_below': previous was at/above the level, now below.
    """
    if trigger_when == "crosses_above":
        return previous_price <= previous_level and current_price > current_level
    elif trigger_when == "crosses_below":
        return previous_price >= previous_level and current_price < current_level
    else:
        logger.warning("Unknown trigger_when: %s", trigger_when)
        return False
