"""WebSocket endpoint for the realtime module — thin entry point only."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from starlette.websockets import WebSocketState

from terminal.auth import service as auth_service
from terminal.database.core import engine
from terminal.dependencies import get_market_manager
from terminal.market_feed.manager import MarketDataManager

from .session import RealtimeSession

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
    manager: MarketDataManager = Depends(get_market_manager),
) -> None:
    """
    Main realtime WebSocket endpoint.

    Authentication is performed during the handshake via a ``token``
    query parameter (``ws://host/ws?token=<jwt>``).  If the token is
    missing or invalid the connection is closed with code **4401**.

    After successful auth, every incoming JSON message is forwarded to
    the :class:`RealtimeSession`.
    """
    # --- Auth ---
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    username = auth_service.verify_token(token)
    if not username:
        await websocket.close(code=4401, reason="Invalid token")
        return

    # Resolve username → User.id (UUID) so DB queries match REST APIs
    from sqlalchemy.orm import Session as SASession

    with SASession(engine) as db:
        user = auth_service.get_by_username(db, username)
    if not user:
        await websocket.close(code=4401, reason="User not found")
        return
    user_id = user.id

    # --- Accept & run ---
    await websocket.accept()
    session = RealtimeSession(websocket, user_id=user_id, manager=manager)
    logger.info("Realtime connection opened for user=%s", user_id)

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
