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
)
from .screener import ScreenerSession
from .quote import QuoteSession

if TYPE_CHECKING:
    from terminal.market_feed.manager import MarketDataManager

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
        self, websocket: WebSocket, *, user_id: str, manager: "MarketDataManager"
    ) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self.manager = manager
        self._screeners: dict[str, ScreenerSession] = {}
        self._quotes: dict[str, QuoteSession] = {}

    def cleanup(self) -> None:
        """Stop all active sub-sessions. Call on WebSocket disconnect."""
        for screener in self._screeners.values():
            screener.stop()
        self._screeners.clear()

        for quote in self._quotes.values():
            quote.stop()
        self._quotes.clear()

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

    # ------------------------------------------------------------------
    # Messaging helpers
    # ------------------------------------------------------------------

    async def send(self, msg: ServerMessage) -> None:
        """Send a ``ServerMessage`` as JSON text over the WebSocket."""
        await self.websocket.send_text(msg.serialize().decode("utf-8"))

    async def send_error(self, message: str) -> None:
        """Send an error message to the client."""
        await self.send(ErrorMessage(p=(message,)))
