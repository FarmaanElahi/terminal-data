import logging
import warnings

from fastapi import FastAPI

from .api import api_router as api_router
from .logging import configure_logging

# Filter out Pydantic migration warnings
warnings.filterwarnings("ignore", message=".*has been moved to.*")

log = logging.getLogger(__name__)

# we configure the logging level and format
configure_logging()


api = FastAPI(title="Terminal Data API")
api.include_router(api_router)


app = FastAPI(title="Terminal App")
app.mount("/api", api)
