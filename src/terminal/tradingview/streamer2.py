import asyncio
import json
import logging
from typing import List, AsyncGenerator, Dict, Any, Optional
from websockets.asyncio.client import connect, ClientConnection
from websockets import Origin
from string import ascii_letters, digits
from random import choices

logger = logging.getLogger(__name__)

_MESSAGE_PREFIX = "~m~"


class TradingViewWorker:
    """
    A single persistent WebSocket worker connected to TradingView.
    Manages active subscriptions (sessions) and routes messages.
    """

    WSS_URL = "wss://data-wdc.tradingview.com/socket.io/websocket?type=chart"
    ORIGIN = "https://in.tradingview.com"

    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.socket: Optional[ClientConnection] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._queues: Dict[str, asyncio.Queue] = {}
        # session_id -> metadata needed for message routing/state tracking
        self._sessions: Dict[str, Dict] = {}
        self.active_session_count = 0
        self._connected = asyncio.Event()

    async def start(self):
        """Starts the worker connection and listener."""
        self._listen_task = asyncio.create_task(self._run_loop())
        await self._connected.wait()
        logger.info(f"[Worker {self.worker_id}] Started and connected.")

    async def stop(self):
        """Stops the worker gracefully."""
        if self._listen_task:
            self._listen_task.cancel()
        if self.socket:
            await self.socket.close()
        logger.info(f"[Worker {self.worker_id}] Stopped.")

    async def _run_loop(self):
        """Main loop handling reconnection and message listening."""
        while True:
            try:
                async with connect(
                    self.WSS_URL,
                    origin=Origin(self.ORIGIN),
                    max_size=None,
                    ping_timeout=60,
                ) as socket:
                    self.socket = socket

                    # Basic auth and locale setup needed for every new connection
                    await self._send(
                        {"m": "set_auth_token", "p": ["unauthorized_user_token"]}
                    )
                    await self._send({"m": "set_locale", "p": ["en", "IN"]})

                    self._connected.set()

                    # On reconnect, we might need to recreate active sessions
                    await self._restore_sessions()

                    async for message in socket:
                        await self._process_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Worker {self.worker_id}] WebSocket error: {e}")
                self._connected.clear()
                await asyncio.sleep(5)  # Reconnect delay

    async def register_session(
        self, session_id: str, queue: asyncio.Queue, session_data: dict
    ):
        """Registers a new session to handle messages."""
        self._queues[session_id] = queue
        self._sessions[session_id] = session_data
        self.active_session_count += 1

    async def unregister_session(self, session_id: str):
        """Cleans up a session."""
        self._queues.pop(session_id, None)
        self._sessions.pop(session_id, None)
        self.active_session_count -= 1

    async def get_session_data(self, session_id: str) -> dict:
        return self._sessions.get(session_id, {})

    async def send_command(self, data: Any):
        """Sends a command safely over the websocket."""
        await self._connected.wait()
        await self._send(data)

    async def _send(self, data: Any):
        if not self.socket:
            return
        if not isinstance(data, list):
            data = [data]
        payload = ""
        for item in data:
            s = json.dumps(item)
            payload += f"{_MESSAGE_PREFIX}{len(s)}{_MESSAGE_PREFIX}{s}"
        try:
            await self.socket.send(payload)
        except Exception as e:
            logger.error(f"[Worker {self.worker_id}] Send error: {e}")

    async def _decode(self, msg: str) -> list:
        decoded = []
        while msg.startswith(_MESSAGE_PREFIX):
            msg = msg[len(_MESSAGE_PREFIX) :]
            sep = msg.find(_MESSAGE_PREFIX)
            length = int(msg[:sep])
            content = msg[
                sep + len(_MESSAGE_PREFIX) : sep + len(_MESSAGE_PREFIX) + length
            ]
            if content.startswith("~h~"):
                if self.socket:
                    await self.socket.send(
                        f"{_MESSAGE_PREFIX}{len(content)}{_MESSAGE_PREFIX}{content}"
                    )
            elif content.startswith("{"):
                decoded.append(json.loads(content))
            msg = msg[sep + len(_MESSAGE_PREFIX) + length :]
        return decoded

    async def _process_message(self, message: str):
        events = await self._decode(message)
        for event in events:
            m = event.get("m")
            p = event.get("p", [])

            if m == "qsd":
                session_id = p[0]
                queue = self._queues.get(session_id)
                if queue:
                    q = p[1]
                    ticker = q.get("n")
                    if q.get("v"):
                        # Yield just the quote data immediately
                        await queue.put(
                            {"type": "quote", "ticker": ticker, "data": q.get("v")}
                        )

            elif m == "timescale_update":
                session_id = p[0]
                queue = self._queues.get(session_id)
                session_data = self._sessions.get(session_id)

                if queue and session_data:
                    series = p[1].get("sds_1")
                    if series and series.get("s"):
                        # Get the ticker we are currently fetching
                        ticker = session_data["keys"][session_data["bar_started"][-1]][
                            "t"
                        ]
                        bars = [s["v"] for s in series.get("s")]
                        await queue.put({"type": "bar", "ticker": ticker, "data": bars})

            elif m == "series_completed":
                session_id = p[0]
                queue = self._queues.get(session_id)
                session_data = self._sessions.get(session_id)

                if queue and session_data:
                    session_data["bar_completed"] += 1

                    # Fetch next symbol if any
                    # 1. Notify that the series for this ticker is completed
                    completed_key = session_data["bar_started"][-1]
                    completed_ticker = session_data["keys"][completed_key]["t"]
                    await queue.put(
                        {"type": "series_completed", "ticker": completed_ticker}
                    )

                    # 2. Check pending or terminate
                    pending = list(
                        set(session_data["keys"].keys())
                        - set(session_data["bar_started"])
                    )
                    if pending:
                        symbol_key = pending[0]
                        meta = session_data["keys"][symbol_key]
                        series_id = f"s{meta['i']}"

                        await self.send_command(
                            {
                                "m": "modify_series",
                                "p": [
                                    session_id,
                                    "sds_1",
                                    series_id,
                                    symbol_key,
                                    session_data["timeframe"],
                                    "",
                                ],
                            }
                        )
                        session_data["bar_started"].append(symbol_key)
                    else:
                        # All completed for this session
                        await queue.put(None)

            elif m in ("symbol_resolved", "symbol_error"):
                session_id = p[0]
                session_data = self._sessions.get(session_id)
                if session_data:
                    if m == "symbol_error":
                        symbol_key = p[1]
                        if symbol_key in session_data["keys"]:
                            del session_data["keys"][symbol_key]

                    session_data["symbol_resolve_count"] += 1

                    # Start fetching series once all symbols are resolved (including errors)
                    if session_data["symbol_resolve_count"] == session_data.get(
                        "total_symbols", len(session_data["keys"])
                    ):
                        pending = list(
                            set(session_data["keys"].keys())
                            - set(session_data["bar_started"])
                        )
                        if pending:
                            symbol_key = pending[0]
                            series_id = f"s{session_data['keys'][symbol_key]['i']}"
                            await self.send_command(
                                {
                                    "m": "create_series",
                                    "p": [
                                        session_id,
                                        "sds_1",
                                        series_id,
                                        symbol_key,
                                        session_data["timeframe"],
                                        1250,
                                    ],
                                }
                            )
                            session_data["bar_started"].append(symbol_key)
                        else:
                            # If all symbols errored out, or no pending
                            await queue.put(None)

    async def _restore_sessions(self):
        """On reconnect, re-register active sessions."""
        for session_id, data in self._sessions.items():
            if session_id.startswith("qs_"):
                await self.send_command(
                    {"m": "quote_create_session", "p": [session_id]}
                )

                # Restore requested fields
                fields = data.get(
                    "fields", ["open_price", "low_price", "high_price", "lp", "volume"]
                )
                await self.send_command(
                    {"m": "quote_set_fields", "p": [session_id, *fields]}
                )

                await self.send_command(
                    {"m": "quote_add_symbols", "p": [session_id, *data["tickers"]]}
                )
            elif session_id.startswith("cs_"):
                # Reset state
                data["bar_completed"] = 0
                data["bar_started"] = []
                data["symbol_resolve_count"] = 0

                await self.send_command(
                    {"m": "chart_create_session", "p": [session_id, ""]}
                )
                await self.send_command(
                    {"m": "switch_timezone", "p": [session_id, "Asia/Kolkata"]}
                )
                reqs = []
                for k, v in data["keys"].items():
                    p = json.dumps({"adjustment": "splits", "symbol": v["t"]})
                    reqs.append({"m": "resolve_symbol", "p": [session_id, k, f"={p}"]})
                await self.send_command(reqs)


class TradingViewClient:
    """
    Manages a pool of WebSocket workers to handle TradingView requests.
    """

    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self.workers: List[TradingViewWorker] = []
        self._started = False

    async def start(self):
        if self._started:
            return
        self.workers = [TradingViewWorker(i) for i in range(self.pool_size)]
        await asyncio.gather(*(w.start() for w in self.workers))
        self._started = True
        logger.info(f"TradingViewClient started with {self.pool_size} workers.")

    async def stop(self):
        await asyncio.gather(*(w.stop() for w in self.workers))
        self._started = False

    def _get_least_loaded_worker(self) -> TradingViewWorker:
        return min(self.workers, key=lambda w: w.active_session_count)

    def _gen_session_id(self, prefix: str):
        return f"{prefix}_{''.join(choices(ascii_letters + digits, k=12))}"

    async def stream_quotes(
        self, tickers: List[str], fields: List[str] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Subscribes to real-time quotes for given tickers.
        Yields `{"ticker": ..., "data": ...}` forever.
        """
        if fields is None:
            fields = [
                "open_price",
                "open_time",
                "low_price",
                "high_price",
                "lp",
                "lp_time",
                "regular_close_time",
                "regular_close",
                "volume",
            ]

        if not self._started:
            await self.start()

        queue = asyncio.Queue()
        session_info = []

        chunk_size = 300
        ticker_chunks = [
            tickers[i : i + chunk_size] for i in range(0, len(tickers), chunk_size)
        ]

        for chunk in ticker_chunks:
            session_id = self._gen_session_id("qs")
            worker = self._get_least_loaded_worker()

            session_data = {"tickers": chunk, "fields": fields}
            await worker.register_session(session_id, queue, session_data)

            await worker.send_command({"m": "quote_create_session", "p": [session_id]})
            await worker.send_command(
                {"m": "quote_set_fields", "p": [session_id, *fields]}
            )
            await worker.send_command(
                {"m": "quote_add_symbols", "p": [session_id, *chunk]}
            )

            session_info.append((session_id, worker, chunk))

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if item["type"] == "quote":
                    yield {item["ticker"]: item["data"]}
        finally:
            for session_id, worker, chunk in session_info:
                await worker.send_command(
                    {"m": "quote_remove_symbols", "p": [session_id, *chunk]}
                )
                await worker.send_command(
                    {"m": "quote_delete_session", "p": [session_id]}
                )
                await worker.unregister_session(session_id)

    async def stream_bars(
        self, tickers: List[str], timeframe: str = "1D"
    ) -> AsyncGenerator[dict, None]:
        """
        Fetches historical bars for multiple tickers.
        Yields completed bars per ticker once done.
        """
        if not self._started:
            await self.start()

        main_chunk = [tickers[i : i + 50] for i in range(0, len(tickers), 50)]
        queue = asyncio.Queue()
        active_tasks = len(main_chunk)
        semaphore = asyncio.Semaphore(6)

        if active_tasks == 0:
            return

        async def worker_task(chunk):
            nonlocal active_tasks
            try:
                async with semaphore:
                    async for item in self._stream_bars_chunk(chunk, timeframe):
                        await queue.put(item)
            except Exception as e:
                logger.error(f"Error in stream_bars chunk task: {e}", exc_info=True)
            finally:
                active_tasks -= 1
                if active_tasks == 0:
                    await queue.put(None)

        for chunk in main_chunk:
            asyncio.create_task(worker_task(chunk))

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    async def _stream_bars_chunk(
        self, tickers: List[str], timeframe: str
    ) -> AsyncGenerator[dict, None]:
        session_id = self._gen_session_id("cs")
        worker = self._get_least_loaded_worker()
        queue = asyncio.Queue()

        keys = {
            f"sds_sym_{i + 1}": {"t": tickers[i], "i": i + 1}
            for i in range(len(tickers))
        }

        session_data = {
            "tickers": tickers,
            "keys": keys,
            "bar_completed": 0,
            "bar_started": [],
            "symbol_resolve_count": 0,
            "total_symbols": len(keys),
            "timeframe": timeframe,
        }

        await worker.register_session(session_id, queue, session_data)

        await worker.send_command({"m": "chart_create_session", "p": [session_id, ""]})
        await worker.send_command(
            {"m": "switch_timezone", "p": [session_id, "Asia/Kolkata"]}
        )

        reqs = []
        for k, v in keys.items():
            p = json.dumps({"adjustment": "splits", "symbol": v["t"]})
            reqs.append({"m": "resolve_symbol", "p": [session_id, k, f"={p}"]})

        await worker.send_command(reqs)

        bars_accumulator = {}

        try:
            while True:
                item = await queue.get()
                logger.debug(f"[Worker Q] Got item: {item}")
                if item is None:
                    break

                if item["type"] == "bar":
                    ticker = item["ticker"]
                    bars_accumulator[ticker] = item["data"] + bars_accumulator.get(
                        ticker, []
                    )
                elif item["type"] == "series_completed":
                    ticker = item["ticker"]
                    if ticker in bars_accumulator:
                        yield {ticker: bars_accumulator.pop(ticker)}
                    else:
                        logger.warning(f"No bars accumulated for {ticker}")
                        yield {ticker: []}
        finally:
            await worker.unregister_session(session_id)


# Global instance
streamer = TradingViewClient()
