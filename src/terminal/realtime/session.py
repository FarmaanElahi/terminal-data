"""Per-connection realtime session with multiplexed sub-sessions."""

import logging
from typing import Any, TYPE_CHECKING

from fastapi import WebSocket
from pydantic import ValidationError

from .models import (
    ErrorMessage,
    MESSAGE_TYPES,
    ScreenerRequest,
    ServerMessage,
    QuoteRequest,
    ChartRequest,
)
from .screener import ScreenerSession
from .quote import QuoteSession
from .chart import ChartSession

if TYPE_CHECKING:
    from terminal.market_feed.manager import MarketDataManager
    from terminal.candles.service import CandleManager

logger = logging.getLogger(__name__)


class RealtimeSession:
    """
    Holds all state for a single WebSocket connection and handles
    every incoming message.

    Sub-sessions (e.g. :class:`ScreenerSession`) are stored by session id
    and multiplexed over the single WebSocket.

    The WebSocket handler delegates **all** messages here via :meth:`handle`.
    """

    def __init__(
        self,
        websocket: WebSocket,
        *,
        user_id: str,
        manager: "MarketDataManager",
        candle_manager: "CandleManager | None" = None,
    ) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self.manager = manager
        self.candle_manager = candle_manager
        self._screeners: dict[str, ScreenerSession] = {}
        self._quotes: dict[str, QuoteSession] = {}
        self._charts: dict[str, ChartSession] = {}
        self._closed = False
        # Set to True when this session holds a ref in the feed_registry.
        # Used by handler.py teardown to know whether to call feed_registry.release().
        self._has_upstox_ref: bool = False

    def cleanup(self) -> None:
        """Stop all active sub-sessions. Call on WebSocket disconnect."""
        self._closed = True
        for screener in self._screeners.values():
            screener.stop()
        self._screeners.clear()

        for quote in self._quotes.values():
            quote.stop()
        self._quotes.clear()

        for chart in self._charts.values():
            chart.stop()
        self._charts.clear()

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    async def handle(self, raw: dict[str, Any]) -> None:
        """Parse and dispatch a single raw JSON message from the client."""
        m = raw.get("m")
        if not m:
            await self.send_error("Missing 'm' field")
            return

        typed_model = MESSAGE_TYPES.get(m)
        if typed_model is None:
            await self.send_error(f"Unknown message type: {m}")
            return

        try:
            msg = typed_model.model_validate(raw)
        except ValidationError as exc:
            await self.send_error(
                f"Invalid {m}: {exc.error_count()} validation error(s)"
            )
            return

        # --- Route ---
        if isinstance(msg, ScreenerRequest):
            await self._route_screener(msg)
        elif isinstance(msg, QuoteRequest):
            await self._route_quote(msg)
        elif isinstance(msg, ChartRequest):
            await self._route_chart(msg)
        else:
            match msg.m:
                case "ping":
                    await self._handle_ping()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_ping(self) -> None:
        """Respond with a pong."""
        await self.send(ServerMessage(m="pong"))

    async def _route_screener(self, msg: ScreenerRequest) -> None:
        """Route a screener request — create session or forward to it."""
        session_id = msg.p[0]

        if msg.m == "create_screener":
            if session_id in self._screeners:
                await self.send_error(f"Screener session {session_id!r} already exists")
                return

            screener = ScreenerSession(session_id, realtime=self)
            self._screeners[session_id] = screener
            logger.info(
                "Created screener session %s for user=%s", session_id, self.user_id
            )
            await self.send(
                ServerMessage(m="screener_session_created", p=(session_id,))
            )

        if msg.m == "destroy_screener":
            screener = self._screeners.pop(session_id, None)
            if screener:
                screener.stop()
                logger.info(
                    "Destroyed screener session %s for user=%s",
                    session_id,
                    self.user_id,
                )
            return

        # All other screener requests are forwarded to the session
        screener = self._screeners.get(session_id)
        if screener is None:
            await self.send_error(f"Screener session {session_id!r} not found")
            return

        await screener.handle(msg)

    async def _route_quote(self, msg: QuoteRequest) -> None:
        """Route a quote request — create session or forward to it."""
        session_id = msg.p[0]

        if msg.m == "create_quote_session":
            if session_id in self._quotes:
                # User asked to create, if it exists we just proceed or error?
                # Usually create_quote_session might be called to reset or just start.
                # Let's stop if exists and recreate to be safe.
                self._quotes[session_id].stop()

            quote_session = QuoteSession(
                session_id, realtime=self, manager=self.manager
            )
            self._quotes[session_id] = quote_session
            logger.info(
                "Created quote session %s for user=%s", session_id, self.user_id
            )
            # User didn't specify a "session_created" message for quotes, but it's good practice.
            # However I will follow the user's specific emit instructions.

        quote_session = self._quotes.get(session_id)
        if quote_session is None:
            await self.send_error(f"Quote session {session_id!r} not found")
            return

        await quote_session.handle(msg)

    async def _route_chart(self, msg: ChartRequest) -> None:
        """Route a chart request — create, modify, or destroy."""
        session_id = msg.p[0]

        if msg.m == "create_chart":
            if session_id in self._charts:
                # Stop existing and recreate
                self._charts[session_id].stop()

            if not self.candle_manager:
                await self.send_error("Chart sessions require candle manager")
                return

            chart = ChartSession(
                session_id,
                realtime=self,
                candle_manager=self.candle_manager,
            )
            self._charts[session_id] = chart
            logger.info(
                "Created chart session %s for user=%s", session_id, self.user_id
            )
            await self.send(ServerMessage(m="chart_session_created", p=(session_id,)))

        if msg.m == "destroy_chart":
            chart = self._charts.pop(session_id, None)
            if chart:
                chart.stop()
                logger.info(
                    "Destroyed chart session %s for user=%s",
                    session_id,
                    self.user_id,
                )
            return

        # Forward to the session
        chart = self._charts.get(session_id)
        if chart is None:
            await self.send_error(f"Chart session {session_id!r} not found")
            return

        await chart.handle(msg)

    # ------------------------------------------------------------------
    # Messaging helpers
    # ------------------------------------------------------------------

    async def send(self, msg: ServerMessage) -> None:
        """Send a ``ServerMessage`` as JSON text over the WebSocket."""
        if self._closed:
            return
        try:
            await self.websocket.send_text(msg.serialize().decode("utf-8"))
        except RuntimeError:
            # WebSocket already closed — mark and ignore
            self._closed = True

    async def send_error(self, message: str) -> None:
        """Send an error message to the client."""
        await self.send(ErrorMessage(p=(message,)))

    async def restart_upstox_feed(self, new_token: str) -> None:
        """Attach or re-attach this session to the user's shared Upstox feed.

        Called by broker/router.py after a successful OAuth token exchange.
        If this session didn't previously hold a registry ref (e.g. the user
        had no token when they connected), we acquire one and hot-plug the
        shared feed into this session's UpstoxClient.
        """
        from terminal.candles.feed_registry import feed_registry

        if not self._has_upstox_ref:
            # First time this session gets a feed — acquire a ref and plug it in
            shared_feed = await feed_registry.acquire(self.user_id, new_token)
            self._has_upstox_ref = True
            if self.candle_manager:
                await self.candle_manager.attach_provider_feed("india", shared_feed)

        await self.send(ServerMessage(
            m="upstox_status",
            p=({"connected": True, "login_required": False},),
        ))
