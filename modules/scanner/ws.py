import json
from typing import Literal, Annotated, Union, Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, TypeAdapter
from modules.scanner.data import query_symbols


class ScreenerSubscribeRequest(BaseModel):
    t: Literal["SCREENER_SUBSCRIBE"]
    session_id: str
    filters: list[dict[str, Any]] = []
    sort: list[dict[str, Any]] = []
    columns: list[str] = []
    range: list[int] = []


class ScreenerUnSubscribeRequest(BaseModel):
    t: Literal["SCREENER_UNSUBSCRIBE"]
    session_id: str


class ScreenerPatchRequest(BaseModel):
    t: Literal["SCREENER_PATCH"]
    session_id: str
    filters: list[dict[str, Any]] | None = None
    sort: list[dict[str, Any]] | None = None
    columns: list[str] | None = None
    range: tuple[int, int] | None = None


# Response

class ScreenerSubscribedResponse(BaseModel):
    t: Literal["SCREENER_SUBSCRIBED"]
    session_id: str


class ScreenerPatchedResponse(BaseModel):
    t: Literal["SCREENER_PATCHED"]
    session_id: str


class ScreenerFullResponse(BaseModel):
    t: Literal["SCREENER_FULL_RESPONSE"]
    session_id: str
    c: list[str]
    d: Any
    range: tuple[int, int]
    total: int


class DuplicateScreenerResponse(BaseModel):
    t: Literal["SCREENER_DUPLICATE"]
    session_id: str


class ErrorResponse(BaseModel):
    t: Literal["SCREENER_ERROR"]
    msg: str


WSSessionRequest = Annotated[
    Union[ScreenerSubscribeRequest, ScreenerPatchRequest, ScreenerUnSubscribeRequest],
    Field(discriminator="t")
]

WSSessionResponse = Annotated[
    Union[ScreenerSubscribedResponse, ScreenerFullResponse, ErrorResponse],
    Field(discriminator="t")
]

adapter = TypeAdapter(WSSessionRequest)


class ScreenerSession:
    ws: WebSocket
    session_id: str
    filters: list[dict[str, Any]] = []
    sort: list[dict[str, Any]] = []
    columns: list[str] = ["ticker", "name", "logo", "day_close"]
    range: (int, int) = (0, -1)

    def __init__(self, ws: WebSocket, session_id: str):
        self.ws = ws
        self.session_id = session_id

    def on_event(self, event):
        pass

    async def subscribe(self, t: ScreenerSubscribeRequest):
        self.columns = ["ticker", "name", "logo", "day_close"] if len(t.columns) == 0 else t.columns
        self.range = (0, -1) if len(t.range) < 2 else t.range
        self.filters = t.filters
        self.sort = t.sort
        await self.ws.send_json(ScreenerSubscribedResponse(t="SCREENER_SUBSCRIBED", session_id=t.session_id).model_dump())

    async def unsubscribe(self, t: ScreenerUnSubscribeRequest):
        pass

    async def patch(self, t: ScreenerPatchRequest):
        is_patched = False

        if t.columns is not None:
            is_patched = True
            self.columns = ["name"] if len(t.columns) == 0 else t.columns

        if t.filters is not None:
            self.filters = t.filters
            is_patched = True

        if t.range is not None:
            is_patched = True
            self.range = t.range

        if t.sort is not None:
            is_patched = True
            self.sort = t.sort

        if is_patched:
            await self.ws.send_json(ScreenerPatchedResponse(t="SCREENER_PATCHED", session_id=self.session_id).model_dump())
            await self.dispatch_full_response()

    async def dispatch_full_response(self):
        (start, end) = self.range
        if end < start or end < 0:
            return

        offset = start
        limit = end - start

        total_result = query_symbols(columns=["ticker"], filter_merge="OR", filters=self.filters)
        total = len(total_result)

        result = query_symbols(
            columns=self.columns,
            filters=self.filters,
            sort_fields=self.sort,
            filter_merge="OR",
            offset=offset,
            limit=limit,
        )
        c = result.columns.tolist()
        d = json.loads(result.to_json(orient="values"))
        await self.ws.send_json(ScreenerFullResponse(
            session_id=self.session_id,
            c=c,
            d=d,
            t="SCREENER_FULL_RESPONSE",
            range=(start, end),
            total=total,
        ).model_dump())


class WSSession:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.ss: dict[str, ScreenerSession] = {}

    async def listen(self):
        try:
            async for data in self.ws.iter_text():
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

    async def on_data(self, event: WSSessionRequest):
        if isinstance(event, ScreenerSubscribeRequest):
            return await self.on_screener_subscribe(event)
        if isinstance(event, ScreenerUnSubscribeRequest):
            return await self.on_screener_unsubscribe(event)
        if isinstance(event, ScreenerPatchRequest):
            return await self.on_screener_patch(event)
        else:
            return await self.ws.send_json({"error": "Unknown event type"})

    async def on_screener_subscribe(self, event: ScreenerSubscribeRequest):
        if event.session_id in self.ss:
            return self.ws.send_json(DuplicateScreenerResponse(t="SCREENER_DUPLICATE", session_id=event.session_id).model_dump())

        screener_ss = ScreenerSession(self.ws, session_id=event.session_id)
        self.ss[event.session_id] = screener_ss
        return await screener_ss.subscribe(event)

    async def on_screener_unsubscribe(self, event: ScreenerUnSubscribeRequest):
        if event.session_id in self.ss:
            await self.ss[event.session_id].unsubscribe(event)
            self.ss.pop(event.session_id)

    async def on_screener_patch(self, event: ScreenerPatchRequest):
        if event.session_id in self.ss:
            await self.ss[event.session_id].patch(event)
