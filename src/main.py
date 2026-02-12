from fastapi import FastAPI
from api.symbols import router as symbols_router
from api.base import router as base_router

app = FastAPI(title="Terminal Data API")

# Include routers
app.include_router(base_router)
app.include_router(symbols_router)
