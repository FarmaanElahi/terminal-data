"""Pydantic models for the realtime WebSocket message protocol.

Client messages use ``m`` (message type) and ``p`` (parameters tuple).
Typed request classes extend :class:`ClientMessage` with a fixed ``m``
literal and a validated ``p`` shape.
"""

from typing import Any, Literal

from pydantic import BaseModel
import orjson

from terminal.column.models import ColumnDef


# ------------------------------------------------------------------
# Client → Server
# ------------------------------------------------------------------


class ClientMessage(BaseModel):
    """Base incoming message from the client over WebSocket."""

    m: str
    p: tuple[Any, ...] | None = None


class PingRequest(ClientMessage):
    """Ping heartbeat — no parameters."""

    m: Literal["ping"]


# ------------------------------------------------------------------
# Screener requests
# ------------------------------------------------------------------


class ScreenerRequest(ClientMessage):
    """Base class for all screener-related requests.

    Any message whose typed model inherits from this class will be
    forwarded to the ``ScreenerSession.handle()`` method.
    """

    p: tuple[str, ...]  # p[0] is always the screener session_id


# ------------------------------------------------------------------
# Screener params
# ------------------------------------------------------------------


class ScreenerParams(BaseModel):
    """Parameters for initializing a screener."""

    source: str | None = None  # list ID
    columns: list[ColumnDef] | None = None  # The actual column configurations
    filter_interval: int = 0  # 0=realtime, >0=seconds (min 5s enforced in logic)
    filter_active: bool = True  # False = skip filtering, emit all symbols


class CreateScreenerRequest(ScreenerRequest):
    """Create a new screener session.

    p structure: (session_id, params)
    """

    m: Literal["create_screener"]
    p: tuple[str, ScreenerParams | None]


class ModifyScreenerRequest(ScreenerRequest):
    """Modify an existing screener session (overwrite params).

    p structure: (session_id, params)
    """

    m: Literal["modify_screener"]
    p: tuple[str, ScreenerParams]


class DestroyScreenerRequest(ScreenerRequest):
    """Destroy an existing screener session.

    p structure: (session_id,)
    """

    m: Literal["destroy_screener"]
    p: tuple[str]


# ------------------------------------------------------------------
# Quote requests
# ------------------------------------------------------------------


class QuoteRequest(ClientMessage):
    """Base class for all quote-related requests.

    Any message whose typed model inherits from this class will be
    forwarded to the ``QuoteSession.handle()`` method.
    """

    p: tuple[str, list[str]]  # p[0] is the session_id, p[1] is list of symbols


class CreateQuoteSessionRequest(QuoteRequest):
    """Create a new quote session.

    p structure: (session_id, symbols)
    """

    m: Literal["create_quote_session"]


class SubscribeSymbolsRequest(QuoteRequest):
    """Subscribe to more symbols in a quote session.

    p structure: (session_id, symbols)
    """

    m: Literal["subscribe_symbols"]


class UnsubscribeSymbolsRequest(QuoteRequest):
    """Unsubscribe symbols from a quote session.

    p structure: (session_id, symbols)
    """

    m: Literal["unsubscribe_symbols"]


# ------------------------------------------------------------------
# Server → Client
# ------------------------------------------------------------------


class ServerMessage(BaseModel):
    """Outgoing message from the server over WebSocket."""

    m: str
    p: tuple[Any, ...] | None = None

    def serialize(self) -> bytes:
        return orjson.dumps(
            self.model_dump(exclude_none=True),
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS,
        )


class ErrorMessage(ServerMessage):
    """Error response.  ``p[0]`` is the error description."""

    m: Literal["error"] = "error"
    p: tuple[str]


class QuoteData(BaseModel):
    """Payload for full_quote."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class FullQuoteResponse(ServerMessage):
    """Initial full quote data emission."""

    m: Literal["full_quote"] = "full_quote"
    p: tuple[str, str, QuoteData]  # session_id, symbol, data


class QuoteUpdateData(BaseModel):
    """Payload for quote_update (only changed fields)."""

    timestamp: int | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None


class QuoteUpdateResponse(ServerMessage):
    """Partial quote data emission."""

    m: Literal["quote_update"] = "quote_update"
    p: tuple[str, str, QuoteUpdateData]  # session_id, symbol, data


# ------------------------------------------------------------------
# Screener responses
# ------------------------------------------------------------------


class ScreenerFilterRow(BaseModel):
    """A single row in the screener filter result."""

    ticker: str
    name: str | None = None
    logo: str | None = None


class ScreenerFilterResponse(ServerMessage):
    """Emitted when the filtered ticker set changes."""

    m: Literal["screener_filter"] = "screener_filter"
    p: tuple[str, list[ScreenerFilterRow], int]  # (session_id, rows, total_count)


class ScreenerValuesResponse(ServerMessage):
    """Emitted with evaluated column values for visible tickers."""

    m: Literal["screener_values"] = "screener_values"
    p: tuple[str, dict[str, list[Any]]]  # (session_id, {col_id: [values]})


# ------------------------------------------------------------------
# Dispatch helper
# ------------------------------------------------------------------

# Map m-type string → typed request model for validation
MESSAGE_TYPES: dict[str, type[ClientMessage]] = {
    "ping": PingRequest,
    "create_screener": CreateScreenerRequest,
    "modify_screener": ModifyScreenerRequest,
    "destroy_screener": DestroyScreenerRequest,
    "create_quote_session": CreateQuoteSessionRequest,
    "subscribe_symbols": SubscribeSymbolsRequest,
    "unsubscribe_symbols": UnsubscribeSymbolsRequest,
}
