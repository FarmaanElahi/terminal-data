# evaluator.py

from typing import Callable
from datetime import datetime, timedelta
from modules.alerts.models import Alert, ChangeUpdate, Point
import operator

# Operator mapping for safe evaluation
OPERATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


def evaluate_alert(alert: Alert, update: ChangeUpdate) -> bool:
    """
    Evaluates whether the alert condition is satisfied for the current price and time.
    """
    current_price = update.ltp
    current_time = update.ltt
    if alert.lhs_type != "last_price":
        print(f"Unsupported lhs_type: {alert.lhs_type}")
        return False

    lhs_value = current_price

    # Determine RHS value based on rhs_type
    if alert.rhs_type == "constant":
        rhs_value = alert.get_constant_value()
        if rhs_value is None:
            print(f"Invalid constant value in alert: {alert.id}")
            return False

    elif alert.rhs_type == "trend_line":
        points = alert.get_trendline_points()
        if not points or len(points) != 2:
            print(f"Invalid trend line in alert: {alert.id}")
            return False
        rhs_value = interpolate_trendline(points[0], points[1], current_time)
        if rhs_value is None:
            print(f"Time {current_time} is outside trendline bounds for alert: {alert.id}")
            return False
    else:
        print(f"Unsupported rhs_type: {alert.rhs_type}")
        return False

    # Evaluate the condition
    op_func: Callable = OPERATORS.get(alert.operator)
    if not op_func:
        print(f"Unsupported operator: {alert.operator}")
        return False

    return op_func(lhs_value, rhs_value)


def interpolate_trendline(point1: Point, point2: Point, ltt: datetime) -> float | None:
    """
    Linearly interpolates between two (timestamp, price) points to get the price at `now`.
    Handles out-of-order time inputs.
    Returns None if `now` is outside the range.
    """

    new, old = (point2, point1) if point2.time > point1.time else (point1, point2)

    if new.time == old.time:
        return new.price

    m = (new.price - old.price) / (new.time.timestamp() - old.time.timestamp())
    p_now = old.price + m * (ltt.timestamp() - old.time.timestamp())

    return p_now
