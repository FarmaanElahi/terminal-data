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
# Chart requests
# ------------------------------------------------------------------


class ChartParams(BaseModel):
    """Parameters for initializing a chart session."""

    symbol: str  # Terminal ticker e.g. NSE:RELIANCE
    interval: str = "1d"  # CandleInterval value e.g. "1m", "1d"
    from_date: str | None = None  # ISO date string YYYY-MM-DD
    to_date: str | None = None  # ISO date string YYYY-MM-DD
    series_id: str | None = None  # Optional series id for tracking


class ChartRequest(ClientMessage):
    """Base class for all chart-related requests.

    Any message whose typed model inherits from this class will be
    forwarded to the ``ChartSession.handle()`` method.
    """

    p: tuple[str, ...]  # p[0] is always the chart session_id


class GetBarRequest(ChartRequest):
    """Direct request for bars with a specific series_id.

    p structure: (session_id, params)
    """

    m: Literal["get_bar"]
    p: tuple[str, ChartParams]


class SubscribeBarRequest(ChartRequest):
    """Subscribe to realtime bars for a series.

    p structure: (session_id, params)
    """

    m: Literal["subscribe_bar"]
    p: tuple[str, ChartParams]


class UnsubscribeBarRequest(ChartRequest):
    """Unsubscribe from realtime bars for a series.

    p structure: (session_id, series_id)
    """

    m: Literal["unsubscribe_bar"]
    p: tuple[str, str]


class CreateChartRequest(ChartRequest):
    """Create a new chart session.
    No longer implies symbol resolution. Just initializes the UI widget context.

    p structure: (session_id, params | None)
    """

    m: Literal["create_chart"]
    p: tuple[str, ChartParams | None]


class ResolveSymbolRequest(ChartRequest):
    """Request to resolve a symbol's metadata.

    p structure: (session_id, ticker)
    """

    m: Literal["resolve_symbol"]
    p: tuple[str, str]


class ModifyChartRequest(ChartRequest):
    """Modify an existing chart session (change symbol or interval).

    p structure: (session_id, params)
    """

    m: Literal["modify_chart"]
    p: tuple[str, ChartParams]


class DestroyChartRequest(ChartRequest):
    """Destroy an existing chart session.

    p structure: (session_id,)
    """

    m: Literal["destroy_chart"]
    p: tuple[str]


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
    v: dict[str, Any] | None = None  # Full row values (id -> value)


class ScreenerFilterResponse(ServerMessage):
    """Emitted when the filtered ticker set changes."""

    m: Literal["screener_filter"] = "screener_filter"
    p: tuple[str, list[ScreenerFilterRow], int]  # (session_id, rows, total_count)


class ScreenerValuesResponse(ServerMessage):
    """Emitted with evaluated column values for visible tickers."""

    m: Literal["screener_values"] = "screener_values"
    p: tuple[str, dict[str, list[Any]]]  # (session_id, {col_id: [values]})


class ScreenerErrorInfo(BaseModel):
    """Describes a formula evaluation error for a column."""

    column_id: str
    message: str


class ScreenerErrorsResponse(ServerMessage):
    """Emitted when formula evaluation errors occur."""

    m: Literal["screener_errors"] = "screener_errors"
    p: tuple[str, list[ScreenerErrorInfo]]  # (session_id, errors)


# ------------------------------------------------------------------
# Chart responses
# ------------------------------------------------------------------


class SymbolResolvedData(BaseModel):
    """Full symbol metadata for TradingView resolveSymbol."""

    name: str
    ticker: str
    description: str | None = None
    type: str = "stock"
    session: str = "0915-1530"
    exchange: str | None = None
    timezone: str = "Asia/Kolkata"  # Standard Indian Time
    pricescale: int = 100
    minmov: int = 1
    has_intraday: bool = True
    has_daily: bool = True
    has_weekly_and_monthly: bool = True
    supported_resolutions: list[str] = [
        "1",
        "3",
        "5",
        "15",
        "30",
        "60",
        "120",
        "240",
        "1D",
        "1W",
        "1M",
    ]
    logo_urls: list[str] | None = None


class SymbolResolvedResponse(ServerMessage):
    """Metadata response for a resolved symbol."""

    m: Literal["symbol_resolved"] = "symbol_resolved"
    p: tuple[str, SymbolResolvedData]  # session_id, metadata


class ChartCandleData(BaseModel):
    """A single candle in the chart series."""

    time: int  # UTC Milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartSeriesResponse(ServerMessage):
    """Full historical candle series for a chart session."""

    m: Literal["chart_series"] = "chart_series"
    p: tuple[
        str, str, str, list[ChartCandleData], str | None, bool
    ]  # session_id, symbol, interval, candles, series_id, no_data


class ChartUpdateResponse(ServerMessage):
    """Real-time candle update for a chart session."""

    m: Literal["chart_update"] = "chart_update"
    p: tuple[
        str, str, ChartCandleData, str | None
    ]  # session_id, symbol, candle, series_id


# ------------------------------------------------------------------
# Alert responses
# ------------------------------------------------------------------


class AlertTriggeredResponse(ServerMessage):
    """Broadcasted when an alert fires."""

    m: Literal["alert_triggered"] = "alert_triggered"
    p: tuple[dict]  # alert_data dict


class AlertStatusChangedResponse(ServerMessage):
    """Broadcasted when an alert's status changes (e.g. auto-deactivation)."""

    m: Literal["alert_status_changed"] = "alert_status_changed"
    p: tuple[dict]  # {alert_id, new_status}


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
    "create_chart": CreateChartRequest,
    "modify_chart": ModifyChartRequest,
    "destroy_chart": DestroyChartRequest,
    "resolve_symbol": ResolveSymbolRequest,
    "get_bar": GetBarRequest,
    "subscribe_bar": SubscribeBarRequest,
    "unsubscribe_bar": UnsubscribeBarRequest,
}
