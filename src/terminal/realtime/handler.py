"""WebSocket endpoint for the realtime module — thin entry point only."""

import asyncio
import logging
from typing import ClassVar

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from starlette.websockets import WebSocketState

from terminal.auth import service as auth_service
from terminal.database.core import engine
from terminal.dependencies import get_market_manager, get_candle_manager
from terminal.market_feed.manager import MarketDataManager
from terminal.candles.service import CandleManager

from .session import RealtimeSession

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
    candle_manager: CandleManager = Depends(get_candle_manager),
) -> None:
    """
    Main realtime WebSocket endpoint.

    Authentication is performed during the handshake via a ``token``
    query parameter (``ws://host/ws?token=<jwt>``).  If the token is
    missing or invalid the connection is closed with code **4401**.

    After successful auth, every incoming JSON message is forwarded to
    the :class:`RealtimeSession`.
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

    # Resolve username -> User.id (UUID) so DB queries match REST APIs
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

    # --- Accept & run ---
    await websocket.accept()
    session = RealtimeSession(
        websocket,
        user_id=user_id,
        manager=manager,
        candle_manager=candle_manager,
    )
    connection_manager.add(user_id, session)
    logger.info(
        "Realtime connection opened for user=%s (total=%d)",
        user_id,
        connection_manager.total_connections,
    )

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
        connection_manager.remove(user_id, session)
