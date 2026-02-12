from fastapi import APIRouter
from terminal.symbols.router import router as symbols_router

api_router = APIRouter()
api_router.include_router(symbols_router)
