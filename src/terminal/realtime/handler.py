"""WebSocket endpoint for the realtime module — thin entry point only."""

import asyncio
import logging
from typing import ClassVar

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from starlette.websockets import WebSocketState

from terminal.auth import service as auth_service
from terminal.database.core import engine
from terminal.dependencies import get_market_manager
from terminal.market_feed.manager import MarketDataManager
from terminal.candles.service import CandleManager
from terminal.candles.upstox import UpstoxClient
from terminal.candles.feed_registry import feed_registry

from .session import RealtimeSession
from .models import ServerMessage

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket connections with limits."""

    MAX_CONNECTIONS: ClassVar[int] = 500
    MAX_PER_USER: ClassVar[int] = 5

    def __init__(self) -> None:
        self._connections: dict[str, list[RealtimeSession]] = {}  # user_id -> sessions
        self._total: int = 0

    @property
    def total_connections(self) -> int:
        return self._total

    def user_count(self, user_id: str) -> int:
        return len(self._connections.get(user_id, []))

    def can_accept(self, user_id: str) -> tuple[bool, str]:
        if self._total >= self.MAX_CONNECTIONS:
            return False, "Server connection limit reached"
        if self.user_count(user_id) >= self.MAX_PER_USER:
            return False, "Per-user connection limit reached"
        return True, ""

    def add(self, user_id: str, session: RealtimeSession) -> None:
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(session)
        self._total += 1

    def remove(self, user_id: str, session: RealtimeSession) -> None:
        sessions = self._connections.get(user_id, [])
        if session in sessions:
            sessions.remove(session)
            self._total -= 1
        if not sessions:
            self._connections.pop(user_id, None)

    def get_sessions(self, user_id: str) -> list[RealtimeSession]:
        return list(self._connections.get(user_id, []))

    async def close_all(self, timeout: float = 10.0) -> None:
        """Send close frame to all sessions with a timeout."""
        tasks = []
        for sessions in self._connections.values():
            for session in sessions:
                tasks.append(self._close_session(session))

        if tasks:
            logger.info("Closing %d WebSocket connections...", len(tasks))
            await asyncio.wait(
                [asyncio.create_task(t) for t in tasks],
                timeout=timeout,
            )

        self._connections.clear()
        self._total = 0

    @staticmethod
    async def _close_session(session: RealtimeSession) -> None:
        try:
            session.cleanup()
            if session.candle_manager:
                await session.candle_manager.close()
            # Release feed registry ref if this session held one
            if session._has_upstox_ref:
                await feed_registry.release(session.user_id)
            if session.websocket.client_state == WebSocketState.CONNECTED:
                await session.websocket.close(code=1001, reason="Server shutting down")
        except Exception:
            pass


# Singleton connection manager — accessible for health checks and shutdown
connection_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
    manager: MarketDataManager = Depends(get_market_manager),
) -> None:
    """
    Main realtime WebSocket endpoint.

    Each session gets its own ``UpstoxClient`` but shares one ``UpstoxFeed``
    per user via the ``feed_registry``. The feed is ref-counted: it starts
    on the first session connect and stops when the last session disconnects.
    """
    # --- Check if shutting down ---
    if getattr(websocket.app, "_shutting_down", False):
        await websocket.close(code=1001, reason="Server shutting down")
        return

    # --- Auth ---
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    username = auth_service.verify_token(token)
    if not username:
        await websocket.close(code=4401, reason="Invalid token")
        return

    from sqlalchemy.orm import Session as SASession

    with SASession(engine) as db:
        user = auth_service.get_by_username(db, username)
    if not user:
        await websocket.close(code=4401, reason="User not found")
        return
    user_id = user.id

    # --- Connection limits ---
    can_accept, reason = connection_manager.can_accept(user_id)
    if not can_accept:
        await websocket.accept()
        await websocket.close(code=4429, reason=reason)
        return

    # --- Load user's Upstox token and acquire shared feed ---
    from terminal.broker import service as broker_service

    user_upstox_token: str | None = None
    try:
        with SASession(engine) as broker_db:
            user_upstox_token = broker_service.get_active_token(broker_db, user_id, "upstox")
    except Exception:
        logger.debug("Could not load Upstox token for user=%s", user_id)

    shared_feed = None
    if user_upstox_token:
        shared_feed = await feed_registry.acquire(user_id, user_upstox_token)

    # UpstoxClient holds a reference to the shared feed (does not own it)
    upstox_client = UpstoxClient(
        access_token=user_upstox_token or "",
        feed=shared_feed,
        owns_feed=False,
    )
    session_candle_manager = CandleManager(providers={"india": upstox_client})

    # --- Accept & run ---
    await websocket.accept()

    session = RealtimeSession(
        websocket,
        user_id=user_id,
        manager=manager,
        candle_manager=session_candle_manager,
    )
    session._has_upstox_ref = shared_feed is not None

    connection_manager.add(user_id, session)
    logger.info(
        "Realtime connection opened for user=%s (total=%d, upstox_feed=%s)",
        user_id,
        connection_manager.total_connections,
        "shared" if shared_feed else "none",
    )

    # Inform the client of the current Upstox feed status
    await session.send(ServerMessage(
        m="upstox_status",
        p=({"connected": feed_registry.is_connected(user_id), "login_required": not bool(user_upstox_token)},),
    ))

    try:
        while True:
            raw = await websocket.receive_json()
            await session.handle(raw)
    except WebSocketDisconnect:
        logger.info("Realtime connection closed for user=%s", user_id)
    except Exception:
        logger.exception("Unexpected error in realtime handler")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011)
    finally:
        session.cleanup()
        had_ref = session._has_upstox_ref

        async def _teardown() -> None:
            await session_candle_manager.close()  # deregisters callback from shared feed
            if had_ref:
                await feed_registry.release(user_id)

        asyncio.create_task(_teardown())
        connection_manager.remove(user_id, session)
