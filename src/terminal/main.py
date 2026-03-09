import warnings
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router as api_router
from .logging import configure_logging
from .realtime.handler import router as realtime_router
from .config import settings
from .health.router import router as health_router
from .middleware import RequestLoggingMiddleware
from .dependencies import get_market_manager, get_fs, get_settings
from .symbols import service as symbols_service
from .proxy import router as proxy_router

logger = logging.getLogger(__name__)

# Filter out Pydantic migration warnings
warnings.filterwarnings("ignore", message=".*has been moved to.*")

# we configure the logging level and format
configure_logging()

# Resolve the built frontend dist directory
# Layout: src/terminal/main.py → parents[1] = src/ → parents[2] = project root
_WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


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

    # ── Alert Engine ─────────────────────────────────────────────────
    from terminal.alerts.engine import AlertEngine
    from terminal.notifications.dispatcher import NotificationDispatcher
    from terminal.dependencies import set_alert_engine

    dispatcher = NotificationDispatcher(
        telegram_bot_token=settings.telegram_bot_token,
        vapid_private_key=settings.vapid_private_key,
        vapid_claims_email=settings.vapid_claims_email,
    )

    alert_engine = AlertEngine(manager)
    alert_engine.set_dispatcher(dispatcher)
    set_alert_engine(alert_engine)

    # Start after a short delay to let MarketDataManager load first
    async def _start_alert_engine():
        await asyncio.sleep(5)  # Let market data load
        await alert_engine.start()

    ae_task = asyncio.create_task(_start_alert_engine())
    ae_task.add_done_callback(lambda t: handle_startup_task(t, "AlertEngine"))
    application.state.alert_engine_task = ae_task

    yield

    # Graceful shutdown sequence
    logger.info("Shutting down...")

    # 1. Stop accepting new WebSocket connections
    application._shutting_down = True  # type: ignore[attr-defined]

    # 2. Close all active WebSocket sessions
    from .realtime.handler import connection_manager

    await connection_manager.close_all(timeout=10.0)

    # 3. Stop AlertEngine
    await alert_engine.stop()
    await dispatcher.close()

    # 4. Stop MarketDataManager polling
    await manager.stop_realtime_streaming()

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

# Proxy /tv/* → charting-library.tradingview-widget.com
# Mounted as a sub-app so the catch-all /{path:path} route is correctly scoped.
# In dev, Vite's proxy (vite.config.ts) intercepts /tv/* before it reaches here.
tv_proxy_app = FastAPI()
tv_proxy_app.include_router(proxy_router)
app.mount("/tv", tv_proxy_app)

app.mount("/api/v1", api)
app.include_router(realtime_router)

# ── Static file serving for the built Vite frontend ──────────────────────────
# Serve the compiled frontend from localhost:8080 in production.
# Falls back to index.html for any path not matched above (SPA routing).
if _WEB_DIST.is_dir():
    # Serve immutable hashed assets directly
    app.mount("/assets", StaticFiles(directory=str(_WEB_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str, request: Request):
        """Catch-all: serve index.html so React Router handles client-side routing."""
        return FileResponse(str(_WEB_DIST / "index.html"))
else:
    logger.warning(
        "Web dist not found at %s — run 'npm run build' in src/web to enable "
        "serving the frontend from FastAPI.",
        _WEB_DIST,
    )
