from fastapi import APIRouter
from terminal.symbols.router import router as symbols_router
from terminal.community.router import router as community_router
from terminal.market_feed.router import router as market_feed_router
from terminal.lists.router import router as lists_router
from terminal.auth.router import auth_router, user_router
from terminal.scan.router import scans as scan_router
from terminal.formula.router import formulas as formula_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(symbols_router)
api_router.include_router(community_router)
api_router.include_router(market_feed_router)
api_router.include_router(lists_router)
api_router.include_router(scan_router)
api_router.include_router(formula_router)
