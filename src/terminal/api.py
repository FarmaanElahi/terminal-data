from fastapi import APIRouter
from terminal.symbols.router import router as symbols_router
from terminal.social_feed.router import router as social_feeds_router
from terminal.market_data.router import router as market_data_router

api_router = APIRouter()
api_router.include_router(symbols_router)
api_router.include_router(social_feeds_router)
api_router.include_router(market_data_router)
