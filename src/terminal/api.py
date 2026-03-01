from fastapi import APIRouter
from terminal.symbols.router import router as symbols_router
from terminal.community.router import router as community_router
from terminal.market_feed.router import router as market_feed_router
from terminal.lists.router import router as lists_router
from terminal.auth.router import auth_router, user_router
from terminal.formula.router import formulas as formula_router
from terminal.condition.router import conditions as condition_router
from terminal.column.router import column_sets as column_set_router
from terminal.boot import router as boot_router
from terminal.candles.router import router as candles_router
from terminal.preferences.router import router as preferences_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(symbols_router)
api_router.include_router(community_router)
api_router.include_router(market_feed_router)
api_router.include_router(lists_router)
api_router.include_router(formula_router)
api_router.include_router(condition_router)
api_router.include_router(column_set_router)
api_router.include_router(boot_router)
api_router.include_router(candles_router)
api_router.include_router(preferences_router)
