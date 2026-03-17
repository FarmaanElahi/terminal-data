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

    def __init__(self, worker_id: int, on_idle: Optional[callable] = None):
        self.worker_id = worker_id
        self.socket: Optional[ClientConnection] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._queues: Dict[str, asyncio.Queue] = {}
        # session_id -> metadata needed for message routing/state tracking
        self._sessions: Dict[str, Dict] = {}
        self.active_session_count = 0
        self.quote_symbols_count = 0
        self.bar_sessions_count = 0
        self.on_idle = on_idle
        self._connected = asyncio.Event()
        self.is_stopping = False

    async def start(self):
        """Starts the worker connection and listener."""
        self._listen_task = asyncio.create_task(self._run_loop())
        await self._connected.wait()
        logger.info(f"[Worker {self.worker_id}] Started and connected.")

    async def stop(self):
        """Stops the worker gracefully."""
        self.is_stopping = True
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
    ) -> bool:
        """Registers a new session. Returns False if the worker is stopping."""
        if self.is_stopping:
            return False
        self._queues[session_id] = queue
        self._sessions[session_id] = session_data
        self.active_session_count += 1
        if session_id.startswith("qs_"):
            self.quote_symbols_count += len(session_data.get("tickers", []))
        elif session_id.startswith("cs_"):
            self.bar_sessions_count += 1
        return True

    async def unregister_session(self, session_id: str):
        """Cleans up a session."""
        session_data = self._sessions.get(session_id, {})
        if session_id.startswith("qs_"):
            self.quote_symbols_count -= len(session_data.get("tickers", []))
        elif session_id.startswith("cs_"):
            self.bar_sessions_count -= 1

        self._queues.pop(session_id, None)
        self._sessions.pop(session_id, None)
        self.active_session_count -= 1

        if self.active_session_count == 0 and self.on_idle:
            # Notify client that this worker can be shut down
            if asyncio.iscoroutinefunction(self.on_idle):
                await self.on_idle(self)
            else:
                self.on_idle(self)

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
                    # IMPORTANT: use deterministic order (not set()) to
                    # avoid attributing bars to the wrong symbol.
                    pending = [
                        k for k in session_data["keys"]
                        if k not in session_data["bar_started"]
                    ]
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
                            ticker = session_data["keys"][symbol_key]["t"]
                            logger.warning(f"Symbol error for {ticker} (key={symbol_key}), skipping.")
                            del session_data["keys"][symbol_key]

                    session_data["symbol_resolve_count"] += 1

                    # Start fetching series once all symbols are resolved (including errors)
                    if session_data["symbol_resolve_count"] == session_data.get(
                        "total_symbols", len(session_data["keys"])
                    ):
                        # IMPORTANT: use deterministic order (not set())
                        # to avoid attributing bars to the wrong symbol.
                        pending = [
                            k for k in session_data["keys"]
                            if k not in session_data["bar_started"]
                        ]
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
                                        session_data.get("bars", 1500),
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
        """Marks the client as started. Workers will be spawned on demand."""
        self._started = True
        logger.info(f"TradingViewClient initialized (Max {self.pool_size} workers).")

    async def stop(self):
        """Stops all active workers."""
        active_workers = list(self.workers)
        await asyncio.gather(*(w.stop() for w in active_workers))
        self.workers = []
        self._started = False

    async def _handle_worker_idle(self, worker: TradingViewWorker):
        """Called when a worker has no active sessions — stop it and remove from pool."""
        await worker.stop()
        if worker in self.workers:
            self.workers.remove(worker)
        logger.debug(f"[Worker {worker.worker_id}] Idle — stopped and removed from pool.")

    async def _get_least_loaded_worker(self, type: str = "quote") -> TradingViewWorker:
        """
        Finds the best worker or spawns a new one based on load thresholds.
        Thresholds:
        - Quote: 1000 symbols
        - Bar: 1 active session
        """
        if not self._started:
            await self.start()

        # Try to find a worker that isn't busy
        available_workers = []
        for w in self.workers:
            if w.is_stopping:
                continue
            if type == "quote" and w.quote_symbols_count < 1000:
                available_workers.append(w)
            elif type == "bar" and w.bar_sessions_count == 0:
                available_workers.append(w)

        if available_workers:
            return min(available_workers, key=lambda w: w.active_session_count)

        # If no available workers and we can spawn more, do so
        if len(self.workers) < self.pool_size:
            worker_id = len(self.workers)
            # Find a non-conflicting ID if some were removed
            existing_ids = {w.worker_id for w in self.workers}
            for i in range(self.pool_size):
                if i not in existing_ids:
                    worker_id = i
                    break

            new_worker = TradingViewWorker(worker_id, on_idle=self._handle_worker_idle)
            self.workers.append(new_worker)
            await new_worker.start()
            return new_worker

        # Fallback to least loaded among all non-stopping workers
        active_workers = [w for w in self.workers if not w.is_stopping]
        if not active_workers:
            # If all are stopping, we must spawn a new one
            return await self._get_least_loaded_worker(type)
        return min(active_workers, key=lambda w: w.active_session_count)

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
            worker = await self._get_least_loaded_worker(type="quote")

            session_data = {"tickers": chunk, "fields": fields}
            if not await worker.register_session(session_id, queue, session_data):
                # Worker was stopping, retry getting a new one
                async for data in self.stream_quotes(tickers, fields):
                    yield data
                return

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
        self, tickers: List[str], timeframe: str = "1D", bars: int = 1500
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
                    async for item in self._stream_bars_chunk(chunk, timeframe, bars=bars):
                        await queue.put(item)
            except Exception as e:
                logger.error(f"Error in stream_bars chunk task: {e}", exc_info=True)
            finally:
                active_tasks -= 1
                if active_tasks == 0:
                    await queue.put(None)

        tasks = []
        for chunk in main_chunk:
            tasks.append(asyncio.create_task(worker_task(chunk)))

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
            # Suppress CancelledError from tasks
            await asyncio.gather(*tasks, return_exceptions=True)
            # Workers clean themselves up via _handle_worker_idle when their
            # session count drops to zero — no need to stop the whole client.

    async def _stream_bars_chunk(
        self, tickers: List[str], timeframe: str, bars: int = 1500
    ) -> AsyncGenerator[dict, None]:
        session_id = self._gen_session_id("cs")
        worker = await self._get_least_loaded_worker(type="bar")
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
            "bars": bars,
        }

        if not await worker.register_session(session_id, queue, session_data):
            # Worker was stopping, recursive retry to pick a new worker
            async for data in self._stream_bars_chunk(tickers, timeframe, bars):
                yield data
            return

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
                    # Bars arrive oldest-first within each batch.
                    # When TradingView sends multiple batches for the same
                    # symbol, earlier batches contain *older* data.
                    # Correct order: existing (older) + new (newer).
                    bars_accumulator[ticker] = bars_accumulator.get(
                        ticker, []
                    ) + item["data"]
                elif item["type"] == "series_completed":
                    ticker = item["ticker"]
                    if ticker in bars_accumulator:
                        yield {ticker: bars_accumulator.pop(ticker)}
                    else:
                        logger.warning(f"No bars accumulated for {ticker}")
                        yield {ticker: []}
        finally:
            await worker.unregister_session(session_id)


class PersistentQuoteSession:
    """Long-lived quote session with dynamic add/remove symbol support.

    Multiple screener sessions share one ``PersistentQuoteSession`` — each
    unique ticker is subscribed on the TradingView WS exactly once,
    regardless of how many screeners are watching it.

    Symbols are distributed across ``qs_*`` sessions (up to CHUNK_SIZE each)
    spread across workers.  All ticks funnel into a single ``asyncio.Queue``
    which is yielded by :meth:`stream`.
    """

    CHUNK_SIZE = 300

    def __init__(self, client: TradingViewClient, fields: List[str] | None = None):
        self._client = client
        self._fields = fields or [
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
        self._queue: asyncio.Queue = asyncio.Queue()
        # session_id -> worker
        self._session_workers: Dict[str, TradingViewWorker] = {}
        # ticker -> session_id (for O(1) lookup on remove)
        self._ticker_to_session: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()

    async def add_symbols(self, tickers: set) -> None:
        """Subscribe to additional tickers (idempotent — skips already-subscribed)."""
        if not tickers:
            return

        # Classify work under the lock — no I/O inside
        add_to_existing: Dict[str, List[str]] = {}  # session_id -> chunk
        new_sessions: List[tuple] = []  # (session_id, chunk)

        async with self._lock:
            pending = [t for t in tickers if t not in self._ticker_to_session]
            if not pending:
                return

            # Fill existing sessions first (up to CHUNK_SIZE each)
            for session_id, worker in list(self._session_workers.items()):
                if not pending:
                    break
                current = worker._sessions.get(session_id, {}).get("tickers", [])
                room = self.CHUNK_SIZE - len(current)
                if room > 0:
                    chunk = pending[:room]
                    pending = pending[room:]
                    add_to_existing[session_id] = chunk
                    current.extend(chunk)
                    worker.quote_symbols_count += len(chunk)
                    for t in chunk:
                        self._ticker_to_session[t] = session_id

            # Allocate new session_ids for remaining tickers
            for i in range(0, len(pending), self.CHUNK_SIZE):
                chunk = pending[i : i + self.CHUNK_SIZE]
                session_id = self._client._gen_session_id("qs")
                new_sessions.append((session_id, chunk))
                for t in chunk:
                    self._ticker_to_session[t] = session_id

        # Send WS commands outside lock
        if not self._client._started:
            await self._client.start()

        for session_id, chunk in add_to_existing.items():
            worker = self._session_workers[session_id]
            await worker.send_command({"m": "quote_add_symbols", "p": [session_id, *chunk]})
            logger.debug("[PQS] Added %d symbols to existing session %s", len(chunk), session_id)

        for session_id, chunk in new_sessions:
            worker = await self._client._get_least_loaded_worker(type="quote")
            session_data: Dict[str, Any] = {"tickers": list(chunk), "fields": self._fields}
            await worker.register_session(session_id, self._queue, session_data)
            async with self._lock:
                self._session_workers[session_id] = worker
            await worker.send_command({"m": "quote_create_session", "p": [session_id]})
            await worker.send_command({"m": "quote_set_fields", "p": [session_id, *self._fields]})
            await worker.send_command({"m": "quote_add_symbols", "p": [session_id, *chunk]})
            logger.debug("[PQS] Created new session %s with %d symbols", session_id, len(chunk))

    async def remove_symbols(self, tickers: set) -> None:
        """Unsubscribe from tickers."""
        if not tickers:
            return

        per_session: Dict[str, List[str]] = {}
        sessions_to_delete: set = set()
        worker_snapshot: Dict[str, TradingViewWorker] = {}

        async with self._lock:
            for t in tickers:
                session_id = self._ticker_to_session.pop(t, None)
                if session_id:
                    per_session.setdefault(session_id, []).append(t)

            for session_id, removed in per_session.items():
                worker = self._session_workers.get(session_id)
                if not worker:
                    continue
                worker_snapshot[session_id] = worker
                removed_set = set(removed)
                current = worker._sessions.get(session_id, {}).get("tickers", [])
                worker._sessions[session_id]["tickers"] = [
                    x for x in current if x not in removed_set
                ]
                worker.quote_symbols_count -= len(removed)
                if not worker._sessions[session_id]["tickers"]:
                    sessions_to_delete.add(session_id)
                    self._session_workers.pop(session_id, None)

        # Send WS commands outside lock
        for session_id, removed in per_session.items():
            worker = worker_snapshot.get(session_id)
            if not worker:
                continue
            if session_id in sessions_to_delete:
                await worker.send_command({"m": "quote_delete_session", "p": [session_id]})
                await worker.unregister_session(session_id)
                logger.debug("[PQS] Deleted empty session %s", session_id)
            else:
                await worker.send_command(
                    {"m": "quote_remove_symbols", "p": [session_id, *removed]}
                )
                logger.debug(
                    "[PQS] Removed %d symbols from session %s", len(removed), session_id
                )

    async def stream(self) -> AsyncGenerator[dict, None]:
        """Yield ``{ticker: quote_data}`` forever until :meth:`stop` is called."""
        while not self._stop_event.is_set():
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if item is None:
                break
            if item.get("type") == "quote":
                yield {item["ticker"]: item["data"]}

    async def stop(self) -> None:
        """Tear down all quote sessions and stop streaming."""
        self._stop_event.set()

        sessions: List[tuple] = []
        async with self._lock:
            for session_id, worker in list(self._session_workers.items()):
                tickers = worker._sessions.get(session_id, {}).get("tickers", [])
                sessions.append((session_id, worker, list(tickers)))
            self._session_workers.clear()
            self._ticker_to_session.clear()

        for session_id, worker, tickers in sessions:
            if tickers:
                await worker.send_command(
                    {"m": "quote_remove_symbols", "p": [session_id, *tickers]}
                )
            await worker.send_command({"m": "quote_delete_session", "p": [session_id]})
            await worker.unregister_session(session_id)

        await self._queue.put(None)
        logger.info("[PQS] Stopped — %d sessions closed.", len(sessions))


# Global instance
streamer = TradingViewClient()
