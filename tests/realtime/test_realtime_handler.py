"""Integration tests for the realtime WebSocket handler."""

import json
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from terminal.auth.security import create_access_token
from terminal.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def valid_token(client: TestClient) -> str:
    """Register a user and get a real JWT token."""
    username = f"ws_test_user_{uuid4().hex[:8]}"
    password = "ws_test_pass"

    register_resp = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert register_resp.status_code == 200
    return create_access_token({"sub": username})


def recv_payload_message(ws) -> dict:
    """Skip broker status broadcasts and return the next request-response payload."""
    while True:
        msg = json.loads(ws.receive_text())
        if msg.get("m") in {"broker_status", "broker_login_required"}:
            continue
        return msg


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
            resp = recv_payload_message(ws)
            assert resp == {"m": "pong"}


# ------------------------------------------------------------------
# Ping
# ------------------------------------------------------------------


class TestPing:
    def test_ping_pong(self, client: TestClient, valid_token: str) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"m": "ping"})
            resp = recv_payload_message(ws)
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
            resp = recv_payload_message(ws)
            assert resp == {"m": "screener_session_created", "p": ["scr1"]}

    def test_create_screener_session_with_params(
        self, client: TestClient, valid_token: str
    ) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            params = {"source": "list_a"}
            ws.send_json({"m": "create_screener", "p": ["scr2", params]})
            resp = recv_payload_message(ws)
            assert resp == {"m": "screener_session_created", "p": ["scr2"]}


# ------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------


class TestErrors:
    def test_unknown_type(self, client: TestClient, valid_token: str) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"m": "foobar"})
            resp = recv_payload_message(ws)
            assert resp["m"] == "error"

    def test_invalid_message(self, client: TestClient, valid_token: str) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"bad": "data"})
            resp = recv_payload_message(ws)
            assert resp["m"] == "error"
            assert "Missing" in resp["p"][0]

    def test_connection_survives_errors(
        self, client: TestClient, valid_token: str
    ) -> None:
        with client.websocket_connect(f"/ws?token={valid_token}") as ws:
            ws.send_json({"bad": "data"})
            recv_payload_message(ws)  # error

            ws.send_json({"m": "ping"})
            resp = recv_payload_message(ws)
            assert resp == {"m": "pong"}
