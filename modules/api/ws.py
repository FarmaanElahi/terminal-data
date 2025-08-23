import asyncio
import json
from typing import Literal, Annotated, Union, Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, TypeAdapter
from modules.api.data import query_symbols
from modules.core.provider.upstox.quotes import fetch_quotes


class AuthenticationRequest(BaseModel):
    t: Literal["AUTH"]
    token: str | Literal["no_auth"] = "no_auth"


class ScreenerSubscribeRequest(BaseModel):
    t: Literal["SCREENER_SUBSCRIBE"]
    session_id: str
    filters: list[dict[str, Any]] = []
    filter_merge: Literal["AND", "OR"] = "OR"
    sort: list[dict[str, Any]] = []
    columns: list[str] = []
    range: list[int] = []
    # When universe is not provided, it will be treated as all symbols(screener) and when it is provided, it will be treated as a watchlist
    universe: list[str] | None = None


class ScreenerSetUniverseRequest(BaseModel):
    t: Literal["SCREENER_SET_UNIVERSE"]
    session_id: str
    # When universe is not provided, it will be treated as all symbols(screener) and when it is provided, it will be treated as a watchlist
    universe: list[str] | None


class ScreenerUnSubscribeRequest(BaseModel):
    t: Literal["SCREENER_UNSUBSCRIBE"]
    session_id: str


class ScreenerPatchRequest(BaseModel):
    t: Literal["SCREENER_PATCH"]
    session_id: str
    filters: list[dict[str, Any]] | None = None
    filter_merge: Literal["AND", "OR"] | None = None
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


class ScreenerPartialResponse(BaseModel):
    t: Literal["SCREENER_PARTIAL_RESPONSE"]
    session_id: str
    d: list[dict[str, Any]]


class DuplicateScreenerResponse(BaseModel):
    t: Literal["SCREENER_DUPLICATE"]
    session_id: str


class ErrorResponse(BaseModel):
    t: Literal["SCREENER_ERROR"]
    msg: str


WSSessionRequest = Annotated[
    Union[AuthenticationRequest, ScreenerSubscribeRequest, ScreenerPatchRequest, ScreenerUnSubscribeRequest, ScreenerSetUniverseRequest],
    Field(discriminator="t")
]

WSSessionResponse = Annotated[
    Union[ScreenerSubscribedResponse, ScreenerFullResponse, ErrorResponse],
    Field(discriminator="t")
]

adapter = TypeAdapter(WSSessionRequest)


class ScreenerSession:
    ws: WebSocket
    token: str | None
    session_id: str
    universe: list[str] | None = None
    filters: list[dict[str, Any]] = []
    filter_merge: Literal["AND", "OR"] = "OR"
    sort: list[dict[str, Any]] = []
    columns: list[str] = ["ticker", "name", "logo", "day_close"]
    range: (int, int) = (0, -1)
    live_symbols: list[dict[str, Any]] = []
    realtime_dispatcher_task: asyncio.Task | None = None

    def __init__(self, ws: WebSocket, session_id: str, token: str | None):
        self.ws = ws
        self.session_id = session_id
        self.token = token

    def on_event(self, event):
        pass

    async def subscribe(self, t: ScreenerSubscribeRequest):
        self.universe = t.universe
        self.columns = ["ticker", "name", "logo", "day_close"] if len(t.columns) == 0 else t.columns
        self.range = (0, -1) if len(t.range) < 2 else t.range
        self.filters = t.filters
        self.filter_merge = t.filter_merge
        # Additional name ensures that pagination is consistent in case of the same value in multiple row
        self.sort = [*t.sort, {"colId": "name", "sort": "ASC"}]
        await self.prefetch_live_symbols()
        await self.ws.send_json(ScreenerSubscribedResponse(t="SCREENER_SUBSCRIBED", session_id=t.session_id).model_dump())
        self.realtime_dispatcher_task = asyncio.create_task(self.dispatch_realtime())

    async def unsubscribe(self):
        if self.realtime_dispatcher_task is not None:
            self.realtime_dispatcher_task.cancel()

    async def patch(self, t: ScreenerPatchRequest):
        is_patched = False

        if t.filter_merge is not None:
            is_patched = True
            self.filter_merge = t.filter_merge

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
            # Additional name ensures that pagination is consistent in case of the same value in multiple row
            self.sort = [*t.sort, {"colId": "name", "sort": "ASC"}]

        if is_patched:
            await self.ws.send_json(ScreenerPatchedResponse(t="SCREENER_PATCHED", session_id=self.session_id).model_dump())
            await self.dispatch_full_response()
            await self.prefetch_live_symbols()

    async def set_universe(self, t: ScreenerSetUniverseRequest):
        self.universe = t.universe
        await self.dispatch_full_response()
        await self.prefetch_live_symbols()

    async def prefetch_live_symbols(self):
        self.live_symbols = query_symbols(
            ["ticker", "name", "isin", "type", "exchange"],
            filters=self.filters, filter_merge=self.filter_merge,
            sort_fields=self.sort,
            universe=self.universe,
        ).to_dict(orient="records")

    async def dispatch_realtime(self):
        while True:
            if self.token is not None and len(self.live_symbols) != 0:
                async for quotes in fetch_quotes(self.live_symbols, token=self.token):
                    updates = quotes
                    await self.ws.send_json(ScreenerPartialResponse(t="SCREENER_PARTIAL_RESPONSE", session_id=self.session_id, d=updates).model_dump())
            await asyncio.sleep(5)

    async def dispatch_full_response(self):
        (start, end) = self.range
        if end < start or end < 0:
            return

        offset = start
        limit = end - start

        total_result = query_symbols(columns=["ticker"], filter_merge=self.filter_merge, filters=self.filters, universe=self.universe)
        total = len(total_result)

        result = query_symbols(
            columns=self.columns,
            filters=self.filters,
            sort_fields=self.sort,
            filter_merge=self.filter_merge,
            offset=offset,
            limit=limit,
            universe=self.universe,
        )
        c = result.columns.tolist()
        d = json.loads(result.to_json(orient="values", date_format="iso"))
        await self.ws.send_json(ScreenerFullResponse(
            session_id=self.session_id,
            c=c,
            d=d,
            t="SCREENER_FULL_RESPONSE",
            range=(start, end),
            total=total,
        ).model_dump())


class WSSession:
    token: str | None = None

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
        for ss in self.ss.values():
            await ss.unsubscribe()
        self.ss.clear()

    async def on_data(self, event: WSSessionRequest):
        if isinstance(event, AuthenticationRequest):
            return await self.on_auth(event)
        if isinstance(event, ScreenerSubscribeRequest):
            return await self.on_screener_subscribe(event)
        if isinstance(event, ScreenerUnSubscribeRequest):
            return await self.on_screener_unsubscribe(event)
        if isinstance(event, ScreenerPatchRequest):
            return await self.on_screener_patch(event)
        if isinstance(event, ScreenerSetUniverseRequest):
            return await  self.on_screener_set_universe(event)
        else:
            return await self.ws.send_json({"error": "Unknown event type"})

    async def on_auth(self, event: AuthenticationRequest):
        if event.token != "no_auth":
            self.token = event.token

    async def on_screener_subscribe(self, event: ScreenerSubscribeRequest):
        if event.session_id in self.ss:
            return self.ws.send_json(DuplicateScreenerResponse(t="SCREENER_DUPLICATE", session_id=event.session_id).model_dump())

        screener_ss = ScreenerSession(self.ws, session_id=event.session_id, token=self.token)
        self.ss[event.session_id] = screener_ss
        return await screener_ss.subscribe(event)

    async def on_screener_unsubscribe(self, event: ScreenerUnSubscribeRequest):
        if event.session_id in self.ss:
            await self.ss[event.session_id].unsubscribe()
            self.ss.pop(event.session_id)

    async def on_screener_patch(self, event: ScreenerPatchRequest):
        if event.session_id in self.ss:
            await self.ss[event.session_id].patch(event)

    async def on_screener_set_universe(self, event: ScreenerSetUniverseRequest):
        if event.session_id in self.ss:
            await self.ss[event.session_id].set_universe(event)
