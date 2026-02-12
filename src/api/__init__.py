from fastapi import FastAPI
from .symbols import router as symbols_router
from .base import router as base_router

app = FastAPI(title="Terminal Data API")

# Include routers
app.include_router(base_router)
app.include_router(symbols_router)
