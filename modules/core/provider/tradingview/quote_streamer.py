import asyncio
import json
import logging
import random
import string
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple

from websockets import Origin, ConnectionClosed
from websockets.asyncio.client import connect

logger = logging.getLogger("TradingViewStreamer")


class QuoteStreamEvent:
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    QUOTE_UPDATE = "quote_update"
    QUOTE_COMPLETED = "quote_completed"
    ERROR = "error"


class TradingViewQuoteStreamer:
    _MESSAGE_PREFIX = "~m~"
    _WEBSOCKET_URL = "wss://data-wdc.tradingview.com/socket.io/websocket?type=chart"
    _ORIGIN = "https://in.tradingview.com"

    def __init__(self,
                 fields: tuple[str] = (),
                 reconnect_delay: int = 5,
                 reconnect_attempts: int = 3):
        self._socket = None
        self._quotes: Dict[str, Dict[str, Any]] = {}
        self._session_id = None
        self._fields = fields
        self._reconnect_delay = reconnect_delay
        self._reconnect_attempts = reconnect_attempts
        self._quote_completed_tickers: set[str] = set()

    def _generate_session_id(self) -> str:
        return f"qs_{''.join(random.choices(string.ascii_letters + string.digits, k=12))}"

    def _encode_message(self, data: Dict[str, Any] | List[Dict[str, Any]] | str) -> str:
        if isinstance(data, str):
            return f"{self._MESSAGE_PREFIX}{len(data)}{self._MESSAGE_PREFIX}{data}"
        if not isinstance(data, list):
            data = [data]
        result = ""
        for item in data:
            payload = json.dumps(item)
            result += f"{self._MESSAGE_PREFIX}{len(payload)}{self._MESSAGE_PREFIX}{payload}"
        return result

    async def _decode_message(self, msg: str) -> List[Dict[str, Any]]:
        decoded = []
        while msg.startswith(self._MESSAGE_PREFIX):
            msg = msg[len(self._MESSAGE_PREFIX):]
            sep = msg.find(self._MESSAGE_PREFIX)
            if sep == -1:
                break
            length = int(msg[:sep])
            start = sep + len(self._MESSAGE_PREFIX)
            end = start + length
            decoded.append(msg[start:end])
            msg = msg[end:]

        events = []
        for m in decoded:
            if m.startswith("~h~"):
                logger.debug(f"Heartbeat received: {m}")
                await self._send_message(m)
            elif m.startswith("{"):
                try:
                    events.append(json.loads(m))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON: {m[:100]}...")
        return events

    async def _send_message(self, data: str | Dict[str, Any] | List[Dict[str, Any]]):
        if not self._socket:
            logger.warning("Socket not connected.")
            return
        try:
            logger.debug(f"SEND {self._encode_message(data)}")
            await self._socket.send(self._encode_message(data))
        except Exception as e:
            logger.error(f"Send error: {e}")
            raise

    async def _initialize_session(self, tickers: List[str]):
        self._session_id = self._generate_session_id()
        await self._send_message({"m": "set_auth_token", "p": ["unauthorized_user_token"]})
        await self._send_message({"m": "set_locale", "p": ["en", "IN"]})
        await self._send_message({"m": "quote_create_session", "p": [self._session_id]})
        await self._send_message({"m": "quote_add_symbols", "p": [self._session_id, *tickers]})
        if self._fields:
            await self._send_message({"m": "quote_set_fields", "p": [self._session_id, *list(self._fields)]})
        logger.info(f"Session {self._session_id} initialized with: {tickers}")

    async def remove_symbols(self, symbols: List[str]):
        if not self._session_id or not self._socket:
            logger.warning("Cannot remove symbols: no session/socket.")
            return
        await self._send_message({"m": "quote_remove_symbols", "p": [self._session_id, *symbols]})
        for s in symbols:
            self._quotes.pop(s, None)
            self._quote_completed_tickers.discard(s)
        logger.info(f"Removed symbols from session {self._session_id}: {symbols}")

    async def _process_quote_update(self, event: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        params = event.get("p", [None, None])
        if len(params) < 2:
            return None
        quote = params[1]
        ticker = quote.get("n")
        values = quote.get("v")
        if not ticker or not values:
            return None
        current = self._quotes.get(ticker, {})
        current.update(values)
        self._quotes[ticker] = current
        return ticker, current.copy()

    async def stream_quotes(self, tickers: List[str]) -> AsyncGenerator[Tuple[str, Optional[str], Any], None]:
        attempts = 0
        while attempts <= self._reconnect_attempts:
            if attempts > 0:
                await asyncio.sleep(self._reconnect_delay)

            try:
                async with connect(
                        self._WEBSOCKET_URL,
                        origin=Origin(self._ORIGIN),
                        max_size=None,
                        ping_timeout=60
                ) as ws:
                    self._socket = ws
                    self._quote_completed_tickers.clear()
                    yield QuoteStreamEvent.CONNECTED, None, {"timestamp": datetime.now().isoformat()}
                    await self._initialize_session(tickers)

                    async for message in ws:
                        for event in await self._decode_message(message):
                            logger.debug(f"RECEIVE {json.dumps(event)}")
                            m = event.get("m")
                            if m == "quote_completed":
                                ticker = event.get("p", [None, None])[1]
                                self._quote_completed_tickers.add(ticker)
                                yield QuoteStreamEvent.QUOTE_COMPLETED, ticker, self._quotes.get(ticker, {})
                            elif m == "qsd":
                                result = await self._process_quote_update(event)
                                if result:
                                    ticker, data = result
                                    if ticker in self._quote_completed_tickers:
                                        yield QuoteStreamEvent.QUOTE_UPDATE, ticker, data
                            elif m in {"critical_error", "protocol_error"}:
                                yield QuoteStreamEvent.ERROR, None, {"message": event.get("p", ["Unknown error"])[0]}

                    break  # Exit if WebSocket closes normally

            except ConnectionClosed as e:
                yield QuoteStreamEvent.DISCONNECTED, None, {"reason": str(e)}
                attempts += 1
            except Exception as e:
                yield QuoteStreamEvent.ERROR, None, {"message": str(e)}
                attempts += 1
            finally:
                self._socket = None

        if attempts > self._reconnect_attempts:
            yield QuoteStreamEvent.ERROR, None, {"message": "Maximum reconnect attempts reached"}
