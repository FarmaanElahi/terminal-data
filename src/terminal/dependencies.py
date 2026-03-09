from collections.abc import Generator
from fsspec import AbstractFileSystem
from functools import lru_cache

from terminal.config import settings
from terminal.database import get_session as db_get_session
from sqlalchemy.orm import Session
from terminal.market_feed.tradingview import TradingViewDataProvider
from terminal.market_feed import OHLCStore, MarketDataManager
from terminal.candles.upstox import UpstoxClient
from terminal.candles.service import CandleManager
from terminal.storage.fs import fs


@lru_cache
def _get_tradingview_provider_instance() -> TradingViewDataProvider:
    """
    Internal helper to provide a memoized TradingViewDataProvider singleton.
    """
    return TradingViewDataProvider(fs=fs, bucket=settings.oci_bucket, cache_dir="data")


@lru_cache
def _get_market_manager_instance() -> MarketDataManager:
    """
    Internal helper to provide a memoized MarketDataManager singleton.
    """
    return MarketDataManager(
        store=OHLCStore(), provider=_get_tradingview_provider_instance()
    )


@lru_cache
def _get_candle_manager_instance() -> CandleManager:
    """Singleton CandleManager for HTTP candle fetching only.

    Real-time feeds are per-session (created in handler.py when a user
    WebSocket connects). This singleton has no feed attached.
    """
    upstox = UpstoxClient(access_token=settings.upstox_access_token or "")
    return CandleManager(providers={"india": upstox})


# Dependencies for FastAPI


def get_fs() -> AbstractFileSystem:
    """
    Provides the OCI filesystem instance.
    """
    return fs


def get_settings():
    """
    Provides the application settings.
    """
    return settings


async def get_session() -> Generator[Session, None, None]:
    """
    Provides a database session from the global engine.
    """
    for session in db_get_session():
        yield session


async def get_tradingview_provider() -> TradingViewDataProvider:
    """
    Provides the global TradingViewDataProvider instance.
    """
    return _get_tradingview_provider_instance()


async def get_market_manager() -> MarketDataManager:
    """
    Provides the global MarketDataManager instance.
    """
    return _get_market_manager_instance()


async def get_candle_manager() -> CandleManager:
    """
    Provides the global CandleManager instance.
    """
    return _get_candle_manager_instance()


# ── Alert Engine ─────────────────────────────────────────────────────────

# The AlertEngine singleton is created in the lifespan (main.py)
# and stored here so the dependency can provide it.
_alert_engine_instance = None


def set_alert_engine(engine) -> None:
    """Store the AlertEngine singleton (called from lifespan)."""
    global _alert_engine_instance
    _alert_engine_instance = engine


def get_alert_engine():
    """Provides the global AlertEngine instance (may be None if not started)."""
    return _alert_engine_instance
