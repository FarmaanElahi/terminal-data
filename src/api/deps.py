from collections.abc import Generator
from functools import lru_cache
from api.config import Settings
from internal.storage import OCIClient
from internal.database import DatabaseHandler
from internal.features.symbols.provider import InMemorySymbolProvider
from sqlmodel import Session


@lru_cache
def get_settings() -> Settings:
    """
    Returns the application settings (memoized).
    """
    return Settings()


@lru_cache
def _get_oci_client() -> OCIClient:
    """
    Internal helper to provide a memoized OCIClient singleton.
    """
    settings = get_settings()
    return OCIClient(oci_config=settings.oci_config, oci_key=settings.oci_key)


@lru_cache
def _get_db_handler() -> DatabaseHandler:
    """
    Internal helper to provide a memoized DatabaseHandler singleton.
    """
    settings = get_settings()
    return DatabaseHandler(database_url=settings.database_url)


@lru_cache
def _get_symbol_provider_instance() -> InMemorySymbolProvider:
    """
    Internal helper to provide a memoized SymbolProvider singleton.
    """
    client = _get_oci_client()
    settings = get_settings()
    # Constructor injection of filesystem and bucket
    return InMemorySymbolProvider(fs=client.get_fs(), bucket=settings.oci_bucket)


# Dependencies for FastAPI


async def get_fs():
    """
    Provides the OCI filesystem instance.
    """
    return _get_oci_client().get_fs()


async def get_session() -> Generator[Session, None, None]:
    """
    Provides a database session.
    """
    db_handler = _get_db_handler()
    for session in db_handler.get_session():
        yield session


async def get_symbol_provider() -> InMemorySymbolProvider:
    """
    Provides the global InMemorySymbolProvider instance.
    """
    return _get_symbol_provider_instance()
