import os
from contextlib import asynccontextmanager
from typing import Literal

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from modules.core.provider.marketsmith.client import MarketSmithClient
from modules.core.provider.stocktwits.client import StockTwitsClient, SymbolFeedParam, GlobalFeedParam
from modules.scanner.models import ScreenerQuery
from modules.scanner.ws import WSSession

load_dotenv()

from modules.scanner.data import refresh_data, get_con, close_con

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_data, "interval", seconds=300)
client = StockTwitsClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # After start
    refresh_data()
    scheduler.start()

    yield
    # Before close
    close_con()
    scheduler.shutdown()
    await client.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/scanner/scan")
async def query_data(q: ScreenerQuery):
    conn = get_con()
    result = conn.execute(q.query).fetchdf()
    return Response(content=result.to_json(orient="records"), media_type="application/json")


@app.websocket("/ws")
async def websocket_connect(websocket: WebSocket):
    await websocket.accept()
    session = WSSession(websocket)
    await session.listen()


@app.get("/symbols/{symbol}")
async def symbol_detail(symbol: str):
    client = MarketSmithClient()
    await client.init_session()
    parts = symbol.split(':')
    if len(parts):
        name = parts[-1].strip()
    else:
        name = symbol.strip()
    return await client.all(name)


@app.get("/ideas/global/{feed}")
async def get_global_feed(
        feed: Literal["trending", "suggested", "popular"],
        limit: int = Query(10, ge=1, le=30),
):
    param = GlobalFeedParam(feed=feed, limit=limit)
    return await client.fetch(param)


# --- Routes ---
@app.get("/ideas/{symbol}/{feed}")
async def get_symbol_feed(
        symbol: str,
        feed: Literal["trending", "popular"],
        limit: int = Query(10, ge=1, le=30),
):
    param = SymbolFeedParam(feed="symbol", filter=feed, symbol=symbol, limit=limit)
    return await client.fetch(param)


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
