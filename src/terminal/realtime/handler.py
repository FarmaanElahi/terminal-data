"""WebSocket endpoint for the realtime module — thin entry point only."""

import asyncio
import logging
from typing import ClassVar

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from starlette.websockets import WebSocketState

from terminal.auth import service as auth_service
from terminal.broker import service as broker_service
from terminal.broker.adapter import Capability
from terminal.broker.feed_registry import feed_registry
from terminal.broker.registry import broker_registry
from terminal.candles.service import CandleManager
from terminal.database.core import engine
from terminal.dependencies import get_market_manager
from terminal.market_feed.manager import MarketDataManager

from .models import ServerMessage
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
            feed_refs = set(session._feed_refs)
            session._feed_refs.clear()
            session.cleanup()
            if session.candle_manager:
                await session.candle_manager.close()
            for provider_id in feed_refs:
                await feed_registry.release(session.user_id, provider_id)
            if session.websocket.client_state == WebSocketState.CONNECTED:
                await session.websocket.close(code=1001, reason="Server shutting down")
        except Exception:
            pass


# Singleton connection manager — accessible for health checks and shutdown
connection_manager = ConnectionManager()


def select_market_providers(
    market_candidates: dict[str, list[str]],
    broker_tokens: dict[str, str | None],
    defaults_map: dict[tuple[str, str], str],
    capability: str = Capability.REALTIME_CANDLES.value,
) -> dict[str, str]:
    """Choose provider per market using user defaults with active-token fallback."""
    selected_market_provider: dict[str, str] = {}
    for market, provider_ids in market_candidates.items():
        available = [pid for pid in provider_ids if broker_tokens.get(pid)]
        if not available:
            continue

        preferred = defaults_map.get((capability, market))
        selected_market_provider[market] = (
            preferred if preferred in available else available[0]
        )

    return selected_market_provider


async def get_active_valid_token(
    *,
    user_id: str,
    adapter,
    broker_db,
) -> str | None:
    credentials = broker_service.list_provider_credentials(
        broker_db,
        user_id,
        adapter.provider_id,
    )
    for credential in credentials:
        token = broker_service.get_credential_token(credential)
        if token and await adapter.validate_token(token):
            return token
    return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
    manager: MarketDataManager = Depends(get_market_manager),
) -> None:
    """Main realtime WebSocket endpoint."""
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

    # --- Load broker tokens, defaults, and select providers ---
    broker_tokens: dict[str, str | None] = {}
    broker_statuses: list[dict[str, object]] = []
    defaults_map: dict[tuple[str, str], str] = {}
    configured_adapters = broker_registry.configured()
    stored_tokens: dict[str, str | None] = {}

    try:
        with SASession(engine) as broker_db:
            defaults_map = broker_service.get_defaults_map(broker_db, user_id)
            for adapter in configured_adapters:
                stored_tokens[adapter.provider_id] = await get_active_valid_token(
                    user_id=user_id,
                    adapter=adapter,
                    broker_db=broker_db,
                )
    except Exception:
        logger.debug("Could not load broker tokens for user=%s", user_id)

    for adapter in configured_adapters:
        token_for_adapter = stored_tokens.get(adapter.provider_id)
        token_is_valid = token_for_adapter is not None
        broker_tokens[adapter.provider_id] = token_for_adapter
        broker_statuses.append(
            {
                "provider_id": adapter.provider_id,
                "display_name": adapter.display_name,
                "markets": [m.value for m in adapter.markets],
                "capabilities": [c.value for c in adapter.capabilities],
                "connected": token_is_valid,
                "login_required": not token_is_valid,
            }
        )

    market_candidates: dict[str, list[str]] = {}
    for adapter in configured_adapters:
        if Capability.REALTIME_CANDLES not in adapter.capabilities:
            continue
        for market in adapter.markets:
            market_candidates.setdefault(market.value, []).append(adapter.provider_id)

    selected_market_provider = select_market_providers(
        market_candidates=market_candidates,
        broker_tokens=broker_tokens,
        defaults_map=defaults_map,
        capability=Capability.REALTIME_CANDLES.value,
    )

    provider_clients: dict[str, object] = {}
    feed_refs: set[str] = set()

    for provider_id in set(selected_market_provider.values()):
        adapter = broker_registry.get(provider_id)
        token_for_adapter = broker_tokens.get(provider_id)
        if adapter is None or not token_for_adapter:
            continue

        shared_feed = await feed_registry.acquire(
            user_id,
            provider_id,
            token_for_adapter,
        )
        if shared_feed is not None:
            feed_refs.add(provider_id)

        candle_provider = adapter.create_candle_provider(token_for_adapter, shared_feed)
        if candle_provider is not None:
            provider_clients[provider_id] = candle_provider

    providers: dict[str, object] = {}
    for market, provider_id in selected_market_provider.items():
        provider = provider_clients.get(provider_id)
        if provider is not None:
            providers[market] = provider

    session_candle_manager = CandleManager(providers=providers)

    # --- Accept & run ---
    await websocket.accept()

    session = RealtimeSession(
        websocket,
        user_id=user_id,
        manager=manager,
        candle_manager=session_candle_manager,
    )
    session._feed_refs = set(feed_refs)

    connection_manager.add(user_id, session)
    logger.info(
        "Realtime connection opened for user=%s (total=%d, providers=%s)",
        user_id,
        connection_manager.total_connections,
        ",".join(sorted(providers.keys())) if providers else "none",
    )

    # Inform the client of current broker statuses and login requirements.
    await session.send(ServerMessage(m="broker_status", p=(broker_statuses,)))
    for status_item in broker_statuses:
        if bool(status_item.get("login_required", False)):
            await session.send(
                ServerMessage(m="broker_login_required", p=(status_item,))
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
        held_refs = set(session._feed_refs)
        session._feed_refs.clear()

        async def _teardown() -> None:
            await session_candle_manager.close()
            for provider_id in held_refs:
                await feed_registry.release(user_id, provider_id)

        asyncio.create_task(_teardown())
        connection_manager.remove(user_id, session)
