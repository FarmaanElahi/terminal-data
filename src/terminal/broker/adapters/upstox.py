from __future__ import annotations

import logging
import time
import urllib.parse
from datetime import datetime, timezone

import httpx
import jwt

from terminal.broker.adapter import (
    BrokerAccountInfo,
    BrokerAdapter,
    Capability,
    Market,
)
from terminal.candles.feed import UpstoxFeed
from terminal.candles.upstox import UpstoxClient
from terminal.config import settings

UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
UPSTOX_AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_PROFILE_URL = "https://api.upstox.com/v2/user/profile"

logger = logging.getLogger(__name__)


class UpstoxAdapter(BrokerAdapter):
    provider_id = "upstox"
    display_name = "Upstox"
    markets = [Market.INDIA]
    capabilities = [Capability.REALTIME_CANDLES]

    def __init__(self) -> None:
        self._token_validation_cache: dict[str, tuple[float, bool]] = {}

    def is_configured(self) -> bool:
        return settings.is_upstox_oauth_configured

    def build_auth_url(self) -> str:
        params = urllib.parse.urlencode(
            {
                "client_id": settings.upstox_api_key,
                "redirect_uri": settings.upstox_redirect_uri,
                "response_type": "code",
            }
        )
        return f"{UPSTOX_AUTH_URL}?{params}"

    async def exchange_code(self, code: str) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                UPSTOX_TOKEN_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "code": code,
                    "client_id": settings.upstox_api_key,
                    "client_secret": settings.upstox_api_secret,
                    "redirect_uri": settings.upstox_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise ValueError(f"No access_token in Upstox response: {data}")
        return token

    async def validate_token(self, token: str) -> bool:
        if not token:
            return False

        now = time.monotonic()
        cached = self._token_validation_cache.get(token)
        if cached and cached[0] > now:
            return cached[1]

        if self._looks_expired(token):
            self._token_validation_cache[token] = (now + 30.0, False)
            return False

        is_valid = await self._validate_token_remote(token)
        self._token_validation_cache[token] = (now + 30.0, is_valid)
        return is_valid

    async def fetch_account_info(self, token: str) -> BrokerAccountInfo | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    UPSTOX_PROFILE_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning("Upstox profile fetch failed: %s", exc)
            return None

        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            data = {}

        account_id = data.get("user_id") or data.get("uid") or data.get("client_id")
        account_owner = data.get("user_name") or data.get("name")
        account_label = data.get("client_id") or data.get("user_id") or data.get("email")
        if not account_label:
            account_label = account_owner

        return BrokerAccountInfo(
            account_id=str(account_id) if account_id else None,
            account_label=str(account_label) if account_label else None,
            account_owner=str(account_owner) if account_owner else None,
            raw_profile=payload if isinstance(payload, dict) else None,
        )

    def create_feed(self, token: str) -> UpstoxFeed:
        return UpstoxFeed(access_token=token)

    def create_candle_provider(
        self,
        token: str,
        feed: UpstoxFeed | None = None,
    ) -> UpstoxClient:
        return UpstoxClient(
            access_token=token,
            feed=feed,
            owns_feed=feed is None,
        )

    @staticmethod
    def _looks_expired(token: str) -> bool:
        """Check JWT exp claim without signature verification."""
        try:
            payload = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                },
            )
        except Exception:
            # Token may be opaque. Treat as unknown and verify via remote call.
            return False

        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return False

        return exp <= datetime.now(timezone.utc).timestamp()

    @staticmethod
    async def _validate_token_remote(token: str) -> bool:
        """Validate token by hitting an authenticated Upstox endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    UPSTOX_PROFILE_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
        except Exception as exc:
            logger.warning("Upstox token validation request failed: %s", exc)
            return False

        if response.status_code in {401, 403}:
            return False
        if response.status_code >= 400:
            logger.warning(
                "Upstox token validation failed with status=%s",
                response.status_code,
            )
            return False

        return True
