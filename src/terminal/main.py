import warnings

from contextlib import asynccontextmanager
import logging
import asyncio

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from .api import api_router as api_router
from .logging import configure_logging
from .realtime.handler import router as realtime_router
from .dependencies import get_market_manager, get_fs, get_settings, get_candle_manager
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
    candle_manager = await get_candle_manager()

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

    candle_task = asyncio.create_task(candle_manager.start_feed())
    candle_task.add_done_callback(lambda t: handle_startup_task(t, "CandleManager"))
    application.state.candle_startup_task = candle_task

    # Preload symbols
    logger.info("Preloading symbols...")
    await symbols_service.init(get_fs(), get_settings())

    yield

    # Shutdown: Stop the streams
    logger.info("Shutting down managers...")
    await manager.stop_realtime_streaming()
    await candle_manager.close()


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

app.mount("/api/v1", api)
app.include_router(realtime_router)
