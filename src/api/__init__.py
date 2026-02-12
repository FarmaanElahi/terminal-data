from fastapi import FastAPI
from .routers.symbols import router as symbols_router

app = FastAPI(title="Terminal Data API")

# Include routers
app.include_router(symbols_router)
