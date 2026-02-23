import warnings

from contextlib import asynccontextmanager
import logging
import asyncio

from fastapi import FastAPI, Depends
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session

from .api import api_router as api_router
from .logging import configure_logging
from .realtime.handler import router as realtime_router
from .dependencies import get_market_manager, get_session
from .auth.router import get_current_user
from .auth.models import User

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


# ─── Boot endpoint: aggregates all user data for fast UI init ────────
@api.get("/boot")
async def boot(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Return all user data needed for UI initialization in a single request."""
    from .lists import service as lists_service
    from .column import service as column_service
    from .condition import service as condition_service
    from .formula import service as formula_service

    lists_service.ensure_default_lists(session, current_user.id)

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "is_active": current_user.is_active,
        },
        "lists": lists_service.all(session, current_user.id),
        "column_sets": column_service.all(session, current_user.id),
        "condition_sets": condition_service.all(session, current_user.id),
        "formulas": formula_service.all(session, current_user.id),
    }


app = FastAPI(title="Terminal App", lifespan=lifespan)

app.mount("/api", api)
app.include_router(realtime_router)
