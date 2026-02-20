import warnings

from fastapi import FastAPI

from .api import api_router as api_router
from .logging import configure_logging
from .realtime.handler import router as realtime_router

# Filter out Pydantic migration warnings
warnings.filterwarnings("ignore", message=".*has been moved to.*")

# we configure the logging level and format
configure_logging()


api = FastAPI(
    title="Dispatch",
    description="Welcome to Terminal's API documentation! Here you will able to discover all of the ways you can interact with the Terminal API.",
    root_path="/api/v1",
    docs_url="/docs",
    openapi_url="/docs/openapi.json",
    redoc_url="/redocs",
)
api.include_router(api_router)


app = FastAPI(title="Terminal App")
app.mount("/api", api)
app.include_router(realtime_router)
