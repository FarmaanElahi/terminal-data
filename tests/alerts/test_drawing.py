"""Unit tests for the drawing geometry resolver."""

from terminal.alerts.drawing import evaluate_drawing_condition


class TestTrendline:
    """Tests for trendline evaluation."""

    def test_crosses_above(self):
        """Price moving from below to above trendline triggers crosses_above."""
        cond = {
            "drawing_type": "trendline",
            "trigger_when": "crosses_above",
            "points": [
                {"time": 1000000, "price": 100.0},
                {"time": 1086400, "price": 110.0},
            ],
        }
        # At t=1043200 (halfway), trendline price ≈ 105
        # At t=1043200-86400 = 956800, previous trendline price ≈ 95
        # Cross detection: previous_close <= prev_trendline(95) AND current_close > current_trendline(105)
        # previous_close=90 (below 95), current_close=107 (above 105) → crosses above
        assert evaluate_drawing_condition(cond, 107.0, 90.0, 1043200) is True

    def test_crosses_above_not_triggered(self):
        """Price staying above trendline doesn't trigger crosses_above."""
        cond = {
            "drawing_type": "trendline",
            "trigger_when": "crosses_above",
            "points": [
                {"time": 1000000, "price": 100.0},
                {"time": 1086400, "price": 110.0},
            ],
        }
        # Both above → no cross
        assert evaluate_drawing_condition(cond, 120.0, 115.0, 1043200) is False

    def test_crosses_below(self):
        """Price moving from above to below trendline triggers crosses_below."""
        cond = {
            "drawing_type": "trendline",
            "trigger_when": "crosses_below",
            "points": [
                {"time": 1000000, "price": 100.0},
                {"time": 1086400, "price": 110.0},
            ],
        }
        # At t=1043200, trendline ~ 105
        # previous_close=107, current_close=103 → crosses below
        assert evaluate_drawing_condition(cond, 103.0, 107.0, 1043200) is True

    def test_degenerate_trendline_same_time(self):
        """Trendline with both points at same time should not crash."""
        cond = {
            "drawing_type": "trendline",
            "trigger_when": "crosses_above",
            "points": [
                {"time": 1000000, "price": 100.0},
                {"time": 1000000, "price": 200.0},
            ],
        }
        # Should treat as hline at avg price (150)
        # previous_close=140, current_close=160 → crosses above 150
        assert evaluate_drawing_condition(cond, 160.0, 140.0, 1000000) is True

    def test_missing_points_returns_false(self):
        """Missing or insufficient points returns False."""
        cond = {
            "drawing_type": "trendline",
            "trigger_when": "crosses_above",
            "points": [{"time": 1000000, "price": 100.0}],
        }
        assert evaluate_drawing_condition(cond, 110.0, 90.0, 1043200) is False


class TestHline:
    """Tests for horizontal line evaluation."""

    def test_crosses_above(self):
        cond = {
            "drawing_type": "hline",
            "trigger_when": "crosses_above",
            "price": 100.0,
        }
        # previous below, current above
        assert evaluate_drawing_condition(cond, 105.0, 95.0, 0) is True

    def test_crosses_above_not_triggered(self):
        cond = {
            "drawing_type": "hline",
            "trigger_when": "crosses_above",
            "price": 100.0,
        }
        # both above → no cross
        assert evaluate_drawing_condition(cond, 105.0, 102.0, 0) is False

    def test_crosses_below(self):
        cond = {
            "drawing_type": "hline",
            "trigger_when": "crosses_below",
            "price": 100.0,
        }
        # previous above, current below
        assert evaluate_drawing_condition(cond, 95.0, 105.0, 0) is True


class TestRectangle:
    """Tests for rectangle zone evaluation."""

    def _rect_cond(self, trigger_when):
        return {
            "drawing_type": "rectangle",
            "trigger_when": trigger_when,
            "top": 110.0,
            "bottom": 90.0,
            "left": 1000000,
            "right": 1086400,
        }

    def test_enters(self):
        """Price entering the rectangle zone."""
        cond = self._rect_cond("enters")
        # previous outside, current inside
        assert evaluate_drawing_condition(cond, 100.0, 80.0, 1043200) is True

    def test_enters_outside_time_range(self):
        """Price entering zone but outside time range should not trigger."""
        cond = self._rect_cond("enters")
        # Outside the time range (too late)
        assert evaluate_drawing_condition(cond, 100.0, 80.0, 2000000) is False

    def test_exits(self):
        """Price exiting the rectangle zone."""
        cond = self._rect_cond("exits")
        # previous inside, current outside
        assert evaluate_drawing_condition(cond, 120.0, 100.0, 1043200) is True

    def test_enters_or_exits(self):
        """Both entering and exiting trigger."""
        cond = self._rect_cond("enters_or_exits")
        # entering
        assert evaluate_drawing_condition(cond, 100.0, 80.0, 1043200) is True
        # exiting
        assert evaluate_drawing_condition(cond, 120.0, 100.0, 1043200) is True


class TestUnknownType:
    """Tests for unknown drawing types."""

    def test_unknown_drawing_type(self):
        cond = {"drawing_type": "unknown", "trigger_when": "crosses_above"}
        assert evaluate_drawing_condition(cond, 100.0, 90.0, 0) is False
