"""Integration tests for the realtime WebSocket handler."""

import jwt
import pytest
from starlette.testclient import TestClient

from terminal.config import settings
from terminal.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def valid_token() -> str:
    """Create a valid JWT for testing."""
    return jwt.encode(
        {"sub": "test_user"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------


class TestAuth:
    def test_missing_token_rejected(self, client: TestClient) -> None:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws") as ws:
                ws.receive_json()

    def test_invalid_token_rejected(self, client: TestClient) -> None:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=bad.token.here") as ws:
                ws.receive_json()

    def test_valid_token_accepted(self, client: TestClient, valid_token: str) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"m": "ping"})
            resp = ws.receive_json()
            assert resp == {"m": "pong"}


# ------------------------------------------------------------------
# Ping
# ------------------------------------------------------------------


class TestPing:
    def test_ping_pong(self, client: TestClient, valid_token: str) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"m": "ping"})
            resp = ws.receive_json()
            assert resp == {"m": "pong"}


# ------------------------------------------------------------------
# Screener
# ------------------------------------------------------------------


class TestScreener:
    def test_create_screener_session(
        self, client: TestClient, valid_token: str
    ) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"m": "create_screener", "p": ["scr1", None]})
            resp = ws.receive_json()
            assert resp == {"m": "screener_session_created", "p": ["scr1"]}

    def test_create_screener_session_with_params(
        self, client: TestClient, valid_token: str
    ) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            params = {"source_list": ["a", "b"]}
            ws.send_json({"m": "create_screener", "p": ["scr2", params]})
            resp = ws.receive_json()
            assert resp == {"m": "screener_session_created", "p": ["scr2"]}


# ------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------


class TestErrors:
    def test_unknown_type(self, client: TestClient, valid_token: str) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"m": "foobar"})
            resp = ws.receive_json()
            assert resp["m"] == "error"

    def test_invalid_message(self, client: TestClient, valid_token: str) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"bad": "data"})
            resp = ws.receive_json()
            assert resp["m"] == "error"
            assert "Missing" in resp["p"][0]

    def test_connection_survives_errors(
        self, client: TestClient, valid_token: str
    ) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"bad": "data"})
            ws.receive_json()  # error

            ws.send_json({"m": "ping"})
            resp = ws.receive_json()
            assert resp == {"m": "pong"}
