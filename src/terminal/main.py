import warnings

from contextlib import asynccontextmanager
import logging
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .api import api_router as api_router
from .logging import configure_logging
from .realtime.handler import router as realtime_router
from .config import settings
from .health.router import router as health_router
from .middleware import RequestLoggingMiddleware
from .dependencies import get_market_manager, get_fs, get_settings
from .symbols import service as symbols_service

logger = logging.getLogger(__name__)

# Filter out Pydantic migration warnings
warnings.filterwarnings("ignore", message=".*has been moved to.*")

# we configure the logging level and format
configure_logging()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup: Start the managers
    manager = await get_market_manager()

    logger.info("Initializing managers...")

    def handle_startup_task(task: asyncio.Task, name: str):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Background %s startup failed", name)

    md_task = asyncio.create_task(manager.start())
    md_task.add_done_callback(lambda t: handle_startup_task(t, "MarketDataManager"))
    application.state.md_startup_task = md_task

    # Preload symbols
    logger.info("Preloading symbols...")
    await symbols_service.init(get_fs(), get_settings())

    yield

    # Graceful shutdown sequence
    logger.info("Shutting down...")

    # 1. Stop accepting new WebSocket connections
    application._shutting_down = True  # type: ignore[attr-defined]

    # 2. Close all active WebSocket sessions
    from .realtime.handler import connection_manager

    await connection_manager.close_all(timeout=10.0)

    # 3. Stop MarketDataManager polling
    await manager.stop_realtime_streaming()

    # 4. Flush pending cache if dirty
    if manager.store.is_dirty:
        logger.info("Flushing dirty cache before shutdown...")
        try:
            import pandas as pd

            all_data = manager.store.get_all_data()
            dfs = []
            for ticker, df in all_data.items():
                if df is None or len(df) == 0:
                    continue
                df_copy = df.copy()
                df_copy["symbol"] = ticker
                df_copy.reset_index(inplace=True)
                dfs.append(df_copy)
            if dfs:
                full_df = pd.concat(dfs, ignore_index=True)
                manager.provider.update_cache(full_df)
                logger.info("Cache flushed successfully.")
        except Exception:
            logger.exception("Failed to flush cache during shutdown")

    logger.info("Shutdown complete.")


api = FastAPI(
    title="Dispatch",
    description="Welcome to Terminal's API documentation! Here you will able to discover all of the ways you can interact with the Terminal API.",
    root_path="/api/v1",
    docs_url="/docs",
    openapi_url="/docs/openapi.json",
    redoc_url="/redocs",
    default_response_class=ORJSONResponse,
)
api.include_router(api_router)

app = FastAPI(title="Terminal App", lifespan=lifespan)

# CORS
_cors_origins = ["*"] if settings.environment == "development" else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health_router)
app.mount("/api/v1", api)
app.include_router(realtime_router)
