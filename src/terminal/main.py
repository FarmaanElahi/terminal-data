import warnings

from contextlib import asynccontextmanager
import logging
import asyncio

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from .api import api_router as api_router
from .logging import configure_logging
from .realtime.handler import router as realtime_router
from .dependencies import get_market_manager, get_fs, get_settings
from .symbols import service as symbols_service

logger = logging.getLogger(__name__)

# Filter out Pydantic migration warnings
warnings.filterwarnings("ignore", message=".*has been moved to.*")

# we configure the logging level and format
configure_logging()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup: Start the market data manager to stream real-time updates
    manager = await get_market_manager()

    logger.info("Initializing MarketDataManager in the background...")

    def handle_startup_task(task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Background md_startup_task failed")

    task = asyncio.create_task(manager.start())
    task.add_done_callback(handle_startup_task)
    application.state.md_startup_task = task

    # Preload symbols
    logger.info("Preloading symbols...")
    await symbols_service.init(get_fs(), get_settings())

    yield

    # Shutdown: Stop the streams
    logger.info("Shutting down MarketDataManager...")
    await manager.stop_realtime_streaming()


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
