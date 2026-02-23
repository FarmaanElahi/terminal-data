from collections.abc import Generator
from fsspec import AbstractFileSystem
from functools import lru_cache

from terminal.config import settings
from terminal.database import get_session as db_get_session
from sqlalchemy.orm import Session
from terminal.market_feed.tradingview import TradingViewDataProvider
from terminal.market_feed import OHLCStore, MarketDataManager
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
