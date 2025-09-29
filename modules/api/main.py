import os
from contextlib import asynccontextmanager
from typing import Literal

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Query
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from modules.api.deps import create_scanner_engine
from modules.api.models import ScreenerQuery
from modules.api.ws import WSSession
from modules.core.provider.marketsmith.client import MarketSmithClient
from modules.core.provider.stocktwits.client import StockTwitsClient, SymbolFeedParam, GlobalFeedParam
from modules.ezscan.models.requests import ScanRequest
from modules.ezscan.models.responses import ScanResponse

load_dotenv()

from modules.api.data import refresh_data, get_con, close_con
from utils.bucket import data_bucket_fs

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_data, "interval", seconds=300)
client = StockTwitsClient()
scanner_engine = create_scanner_engine(data_bucket_fs)


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
    return Response(content=result.to_json(orient="records", date_format="iso"), media_type="application/json")


@app.post("/v2/scan", response_model=ScanResponse)
def scan(request: ScanRequest):
    """Execute technical scan."""
    try:
        result = scanner_engine.scan(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/scan/refresh/{market}")
def scan(market: Literal["india", "us"]):
    """Execute technical scan."""
    try:
        scanner_engine.refresh_data(market)
        return "Scanner Refreshed"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        limit: int = Query(10, ge=1, le=100),
):
    param = GlobalFeedParam(feed=feed, limit=limit)
    return await client.fetch(param)


# --- Routes ---
@app.get("/ideas/{symbol}/{feed}")
async def get_symbol_feed(
        symbol: str,
        feed: Literal["trending", "popular"],
        limit: int = Query(10, ge=1, le=100),
):
    param = SymbolFeedParam(feed="symbol", filter=feed, symbol=symbol, limit=limit)
    return await client.fetch(param)


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
