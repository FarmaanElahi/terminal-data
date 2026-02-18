from collections.abc import Generator
from functools import lru_cache
from terminal.config import settings as global_settings, Settings
from terminal.storage.service import OCIClient

from terminal.database import get_session as db_get_session
from sqlmodel import Session
from terminal.market_feed.tradingview import TradingViewDataProvider
from terminal.market_feed import OHLCStore, MarketDataManager


@lru_cache
def get_settings() -> Settings:
    """
    Returns the application settings.
    """
    return global_settings


@lru_cache
def _get_oci_client() -> OCIClient:
    """
    Internal helper to provide a memoized OCIClient singleton.
    """
    settings = get_settings()
    return OCIClient(oci_config=settings.oci_config, oci_key=settings.oci_key)


@lru_cache
def _get_tradingview_provider_instance() -> TradingViewDataProvider:
    """
    Internal helper to provide a memoized TradingViewDataProvider singleton.
    """
    client = _get_oci_client()
    settings = get_settings()
    return TradingViewDataProvider(
        fs=client.get_fs(), bucket=settings.oci_bucket, cache_dir="data"
    )


@lru_cache
def _get_ohlc_store_instance() -> OHLCStore:
    """
    Internal helper to provide a memoized OHLCStore singleton.
    """
    return OHLCStore()


@lru_cache
def _get_market_manager_instance() -> MarketDataManager:
    """
    Internal helper to provide a memoized MarketDataManager singleton.
    """
    store = _get_ohlc_store_instance()
    provider = _get_tradingview_provider_instance()
    return MarketDataManager(store=store, provider=provider)


# Dependencies for FastAPI


async def get_fs():
    """
    Provides the OCI filesystem instance.
    """
    return _get_oci_client().get_fs()


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
