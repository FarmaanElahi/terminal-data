import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from modules.scanner.models import ScreenerQuery
from pydantic import TypeAdapter

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


@app.websocket("/ws")
async def websocket_connect(websocket: WebSocket):
    await websocket.accept()
    session = WSSession(websocket)
    await session.listen()


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Literal, Annotated, Union


class ScreenerInitEvent(BaseModel):
    event: Literal["SCREENER_INIT"]
    screener_session_id: str
    columns: list[str] = []
    conditions: list[str] = []


class ScreenerSubscribedEvent(BaseModel):
    event: Literal["SCREENER_SUBSCRIBED"]
    msg: str | None = None


class ScreenerErrorEvent(BaseModel):
    event: Literal["SCREENER_ERROR"]
    msg: str


WSSessionEvent = Annotated[
    Union[ScreenerInitEvent, ScreenerErrorEvent, ScreenerSubscribedEvent],
    Field(discriminator="event")
]
adapter = TypeAdapter(WSSessionEvent)


class ScreenerSession:
    EVENT_SCREENER_INIT = "SCREENER_INIT"
    ws: WebSocket

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.conditions: list[dict] = []
        self.columns: list[str] = []

    def on_event(self, event):
        pass

    async def init_session(self, conditions=None, columns=None):
        self.conditions = conditions or []
        self.columns = columns or []
        await self.ws.send_json(ScreenerSubscribedEvent(event="SCREENER_SUBSCRIBED").model_dump())

    def set_conditions(self, conditions):
        self.conditions = conditions

    def set_columns(self, columns):
        self.columns = columns

    def evaluate(self):
        pass

    @staticmethod
    def dispatch_error(ws: WebSocket, msg: str):
        ws.send_json(ScreenerErrorEvent(event="SCREENER_ERROR", msg=msg).model_dump())


class WSSession:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.ss: dict[str, ScreenerSession] = {}

    async def listen(self):
        try:
            while True:
                data = await self.ws.receive_text()
                try:
                    event_obj = adapter.validate_json(data)
                    await self.on_data(event_obj)
                except Exception as e:
                    print(e)
                    await self.ws.send_json({"error": str(e)})
        except WebSocketDisconnect:
            await self.on_disconnect()

    async def on_disconnect(self):
        print("Client disconnected")

    async def on_data(self, event: WSSessionEvent):
        if isinstance(event, ScreenerInitEvent):
            return await self.on_screener_init(event)
        else:
            return await self.ws.send_json({"error": "Unknown event type"})

    async def on_screener_init(self, event: ScreenerInitEvent):
        print("Screener received:", event)
        if event.screener_session_id in self.ss:
            return ScreenerSession.dispatch_error(ws=self.ws, msg="Duplicate screener session")

        screener_ss = ScreenerSession(self.ws)
        self.ss[event.screener_session_id] = screener_ss
        return await screener_ss.init_session(columns=event.columns, conditions=event.conditions)
