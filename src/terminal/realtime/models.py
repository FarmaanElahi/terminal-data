"""Pydantic models for the realtime WebSocket message protocol.

Client messages use ``m`` (message type) and ``p`` (parameters tuple).
Typed request classes extend :class:`ClientMessage` with a fixed ``m``
literal and a validated ``p`` shape.
"""

from typing import Any, Literal

from pydantic import BaseModel


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
# Screener condition models
# ------------------------------------------------------------------


class ScreenerCondition(BaseModel):
    """A single screener condition."""

    expr: str
    evaluated_at: Literal["now", "x_bar_ago", "within_last", "in_row"] = "now"
    evaluated_at_param: int | None = None
    evaluation_type: Literal["boolean", "rank"] = "boolean"
    condition_type: Literal["computed", "static"] = "computed"
    rank_min: int | None = None
    rank_max: int | None = None


class ScreenerParams(BaseModel):
    """Parameters for initializing a screener."""

    source_list: list[str] = []
    conditions: list[ScreenerCondition] = []
    conditional_logic: Literal["and", "or"] = "and"
    pre_conditions: list[ScreenerCondition] = []
    pre_condition_logic: Literal["and", "or"] = "and"


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


class ErrorMessage(ServerMessage):
    """Error response.  ``p[0]`` is the error description."""

    m: Literal["error"] = "error"
    p: tuple[str]


# ------------------------------------------------------------------
# Dispatch helper
# ------------------------------------------------------------------

# Map m-type string → typed request model for validation
MESSAGE_TYPES: dict[str, type[ClientMessage]] = {
    "ping": PingRequest,
    "create_screener": CreateScreenerRequest,
    "modify_screener": ModifyScreenerRequest,
    "create_quote_session": CreateQuoteSessionRequest,
    "subscribe_symbols": SubscribeSymbolsRequest,
    "unsubscribe_symbols": UnsubscribeSymbolsRequest,
}
