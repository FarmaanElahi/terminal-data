from functools import cached_property


class TradingView:
    """
    Unified entry point for TradingView interactions.
    Logic is lazily initialized to avoid unnecessary overhead.
    """

    @cached_property
    def scanner(self):
        from .scanner import TradingViewScanner

        return TradingViewScanner()

    @cached_property
    def streamer(self):
        from .streamer2 import streamer as global_streamer

        return global_streamer


__all__ = ["TradingView", "TradingViewScanner", "TradingViewClient"]
