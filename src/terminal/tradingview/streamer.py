import json
import logging
from typing import List, Any, Literal, AsyncGenerator
from websockets.asyncio.client import connect, ClientConnection
from websockets import Origin
from string import ascii_letters, digits
from random import choices
from asyncio import create_task, gather

logger = logging.getLogger(__name__)

_MESSAGE_PREFIX = "~m~"


class TradingViewStreamer:
    """
    Handles all WebSocket communication with TradingView.
    Logic ported from the proven old codebase.
    """

    WSS_URL = "wss://data-wdc.tradingview.com/socket.io/websocket?type=chart"
    ORIGIN = "https://in.tradingview.com"

    async def fetch_bulk(
        self, tickers: List[str], mode: Literal["quote", "bar", "all"] = "all"
    ) -> AsyncGenerator[tuple[dict, dict], None]:
        """
        Fetches data for multiple tickers in chunks.
        """
        main_chunk = [tickers[i : i + 450] for i in range(0, len(tickers), 450)]
        for idx, chunk in enumerate(main_chunk):
            sub_chunks = [chunk[i : i + 150] for i in range(0, len(chunk), 150)]
            tasks = [create_task(self._fetch_data(sub, mode)) for sub in sub_chunks]
            chunk_results = await gather(*tasks)
            for sub, result in zip(sub_chunks, chunk_results):
                if result:
                    yield result
                else:
                    logger.error(f"Failed chunk: {sub[:5]}...")

    async def _fetch_data(self, tickers: list[str], mode: str):
        if not tickers:
            return {}, {}
        data = {}
        complete = False
        try:
            async with connect(
                self.WSS_URL,
                origin=Origin(self.ORIGIN),
                max_size=None,
                ping_timeout=60,
            ) as socket:
                await self._init_session(socket, tickers, data, mode)
                async for message in socket:
                    complete = await self._process_data(socket, tickers, message, data)
                    if complete:
                        break
        except Exception as e:
            logger.error(f"WebSocket error in _fetch_data: {e}")

        if complete:
            return data.get("quotes", {}), data.get("bars", {})
        return None

    async def _init_session(
        self, socket: ClientConnection, tickers: list[str], data: dict, mode: str
    ):
        qs_session = self._gen_session_id("qs")
        cs_session = self._gen_session_id("cs")
        keys = {
            f"sds_sym_{i + 1}": {"t": tickers[i], "i": i + 1}
            for i in range(len(tickers))
        }

        data.update(
            {
                "quotes": {},
                "bars": {},
                "bar_completed": 0,
                "bar_started": [],
                "quote_completed": 0,
                "symbol_resolve_count": 0,
                "qs": qs_session,
                "cs": cs_session,
                "keys": keys,
            }
        )

        await self._send(
            socket, {"m": "set_auth_token", "p": ["unauthorized_user_token"]}
        )
        await self._send(socket, {"m": "set_locale", "p": ["en", "IN"]})

        if mode in ["all", "quote"]:
            await self._send(socket, {"m": "quote_create_session", "p": [qs_session]})
            await self._send(
                socket, {"m": "quote_add_symbols", "p": [qs_session, *tickers]}
            )
        else:
            data["quote_completed"] = len(tickers)

        if mode in ["all", "bar"]:
            await self._send(
                socket, {"m": "chart_create_session", "p": [cs_session, ""]}
            )
            await self._send(
                socket, {"m": "switch_timezone", "p": [cs_session, "Asia/Kolkata"]}
            )
            reqs = []
            for k, v in keys.items():
                p = json.dumps({"adjustment": "splits", "symbol": v["t"]})
                reqs.append({"m": "resolve_symbol", "p": [cs_session, k, f"={p}"]})
            await self._send(socket, reqs)
        else:
            data["bar_completed"] = len(tickers)

    async def _process_data(
        self, socket: ClientConnection, tickers: list[str], message: str, data: dict
    ):
        events = await self._decode(socket, message)
        for event in events:
            m = event.get("m")
            if m == "qsd":
                q = event.get("p")[1]
                ticker = q.get("n")
                if q.get("v"):
                    data["quotes"][ticker] = data["quotes"].get(ticker, {}) | q.get("v")
            elif m == "quote_completed":
                data["quote_completed"] += 1
            elif m == "symbol_resolved":
                await self._on_symbol_resolved(socket, data)
            elif m == "timescale_update":
                await self._on_timescale_update(event, data)
            elif m == "series_completed":
                await self._on_series_completed(socket, tickers, data)

        return data.get("quote_completed", 0) == len(tickers) and data.get(
            "bar_completed", 0
        ) == len(tickers)

    async def _on_symbol_resolved(self, socket: ClientConnection, data: dict):
        data["symbol_resolve_count"] += 1
        if data["symbol_resolve_count"] != len(data["keys"]):
            return

        pending = list(set(data["keys"].keys()) - set(data["bar_started"]))
        if not pending:
            return

        symbol_key = pending[0]
        series_id = f"s{data['keys'][symbol_key]['i']}"
        await self._send(
            socket,
            {
                "m": "create_series",
                "p": [data["cs"], "sds_1", series_id, symbol_key, "1D", 1250],
            },
        )
        data["bar_started"].append(symbol_key)

    async def _on_timescale_update(self, event: dict, data: dict):
        series = event.get("p")[1].get("sds_1")
        if not series or not series.get("s"):
            return

        ticker = data["keys"][data["bar_started"][-1]]["t"]
        data["bars"][ticker] = [s["v"] for s in series.get("s")] + data["bars"].get(
            ticker, []
        )

    async def _on_series_completed(
        self, socket: ClientConnection, tickers: list[str], data: dict
    ):
        data["bar_completed"] += 1
        if data["bar_completed"] == len(tickers):
            return

        pending = list(set(data["keys"].keys()) - set(data["bar_started"]))
        if not pending:
            return

        symbol_key = pending[0]
        meta = data["keys"][symbol_key]
        series_id = f"s{meta['i']}"

        await self._send(
            socket,
            {
                "m": "modify_series",
                "p": [data["cs"], "sds_1", series_id, symbol_key, "1D", ""],
            },
        )
        data["bar_started"].append(symbol_key)

    async def _decode(self, socket: ClientConnection, msg: str) -> list:
        decoded = []
        while msg.startswith(_MESSAGE_PREFIX):
            msg = msg[len(_MESSAGE_PREFIX) :]
            sep = msg.find(_MESSAGE_PREFIX)
            length = int(msg[:sep])
            content = msg[
                sep + len(_MESSAGE_PREFIX) : sep + len(_MESSAGE_PREFIX) + length
            ]
            if content.startswith("~h~"):
                await socket.send(
                    f"{_MESSAGE_PREFIX}{len(content)}{_MESSAGE_PREFIX}{content}"
                )
            elif content.startswith("{"):
                decoded.append(json.loads(content))
            msg = msg[sep + len(_MESSAGE_PREFIX) + length :]
        return decoded

    async def _send(self, socket: ClientConnection, data: Any):
        if not isinstance(data, list):
            data = [data]
        payload = ""
        for item in data:
            s = json.dumps(item)
            payload += f"{_MESSAGE_PREFIX}{len(s)}{_MESSAGE_PREFIX}{s}"
        await socket.send(payload)

    def _gen_session_id(self, prefix: str):
        return f"{prefix}_{''.join(choices(ascii_letters + digits, k=12))}"
