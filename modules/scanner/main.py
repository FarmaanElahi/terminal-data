from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from modules.scanner.models import ScreenerQuery

load_dotenv()

from modules.scanner.data import refresh_data, get_con, close_con

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_data, "interval", seconds=300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # After start
    refresh_data()
    scheduler.start()

    yield
    # Before close
    close_con()
    scheduler.shutdown()


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


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
