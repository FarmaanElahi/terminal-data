"""Unit tests for RealtimeSession."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from terminal.realtime.session import RealtimeSession


@pytest.fixture
def ws_mock() -> AsyncMock:
    """Fake WebSocket that records send_json calls."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def manager_mock() -> MagicMock:
    return MagicMock()


@pytest.fixture
def session(ws_mock: AsyncMock, manager_mock: MagicMock) -> RealtimeSession:
    return RealtimeSession(ws_mock, user_id="test_user", manager=manager_mock)


# ------------------------------------------------------------------
# Message dispatch
# ------------------------------------------------------------------


class TestPing:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_ping_pong(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        await session.handle({"m": "ping"})
        ws_mock.send_json.assert_awaited_once_with({"m": "pong"})


class TestUnknownType:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_unknown_type(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        await session.handle({"m": "foobar"})
        sent = ws_mock.send_json.call_args[0][0]
        assert sent["m"] == "error"
        assert "Unknown" in sent["p"][0]


class TestInvalidMessage:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_missing_m_field(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        await session.handle({"bad": "data"})
        sent = ws_mock.send_json.call_args[0][0]
        assert sent["m"] == "error"
        assert "Missing" in sent["p"][0]


# ------------------------------------------------------------------
# Screener session
# ------------------------------------------------------------------


class TestCreateScreenerSession:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_screener_no_params(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        await session.handle({"m": "create_screener", "p": ["scr1", None]})
        ws_mock.send_json.assert_awaited_once_with(
            {"m": "screener_session_created", "p": ("scr1",)}
        )
        assert "scr1" in session._screeners
        assert session._screeners["scr1"].params.source is None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_screener_with_params(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        params = {"source": "list1"}
        await session.handle({"m": "create_screener", "p": ["scr2", params]})

        ws_mock.send_json.assert_awaited_once_with(
            {"m": "screener_session_created", "p": ("scr2",)}
        )
        assert "scr2" in session._screeners
        assert session._screeners["scr2"].params.source == "list1"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_duplicate_screener_rejected(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        await session.handle({"m": "create_screener", "p": ["scr1", None]})
        ws_mock.reset_mock()

        await session.handle({"m": "create_screener", "p": ["scr1", None]})
        sent = ws_mock.send_json.call_args[0][0]
        assert sent["m"] == "error"
        assert "already exists" in sent["p"][0]


class TestModifyScreener:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_modify_screener_success(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        # Create first
        await session.handle({"m": "create_screener", "p": ["scr1", None]})
        ws_mock.reset_mock()

        # Modify
        new_params = {"source": "list_updated", "column_set_id": "cs1"}
        await session.handle({"m": "modify_screener", "p": ["scr1", new_params]})

        # No response expected for modify
        ws_mock.send_json.assert_not_called()
        assert session._screeners["scr1"].params.source == "list_updated"
        assert session._screeners["scr1"].params.column_set_id == "cs1"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_modify_unknown_screener(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        params = {"source": "list1"}
        await session.handle({"m": "modify_screener", "p": ["unknown", params]})

        sent = ws_mock.send_json.call_args[0][0]
        assert sent["m"] == "error"
        assert "not found" in sent["p"][0]


# ------------------------------------------------------------------
# Identity
# ------------------------------------------------------------------


class TestIdentity:
    def test_user_id_stored(self, session: RealtimeSession) -> None:
        assert session.user_id == "test_user"


# ------------------------------------------------------------------
# Messaging helpers
# ------------------------------------------------------------------


class TestMessaging:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_send_error(
        self, session: RealtimeSession, ws_mock: AsyncMock
    ) -> None:
        await session.send_error("bad input")
        ws_mock.send_json.assert_awaited_once_with({"m": "error", "p": ("bad input",)})
