from __future__ import annotations

import hashlib
import logging
import time
import urllib.parse

import httpx

from terminal.broker.adapter import (
    BrokerAccountInfo,
    BrokerAdapter,
    Capability,
    Market,
)
from terminal.config import settings

logger = logging.getLogger(__name__)

KITE_AUTH_URL = "https://kite.zerodha.com/connect/login"
KITE_TOKEN_URL = "https://api.kite.trade/session/token"
KITE_PROFILE_URL = "https://api.kite.trade/user/profile"


class KiteAdapter(BrokerAdapter):
    provider_id = "kite"
    display_name = "Zerodha Kite"
    markets = [Market.INDIA]
    capabilities = [
        Capability.ALERTS,
        Capability.ORDER_MANAGEMENT,
        Capability.POSITIONS,
        Capability.HOLDINGS,
    ]

    def __init__(self) -> None:
        self._token_validation_cache: dict[str, tuple[float, bool]] = {}

    def is_configured(self) -> bool:
        return settings.is_kite_oauth_configured

    def build_auth_url(self) -> str:
        params = urllib.parse.urlencode(
            {
                "v": "3",
                "api_key": settings.kite_api_key,
            }
        )
        return f"{KITE_AUTH_URL}?{params}"

    async def exchange_code(self, code: str) -> str:
        """Kite uses request_token in callback; code parameter maps to it."""
        request_token = code
        checksum_src = f"{settings.kite_api_key}{request_token}{settings.kite_api_secret}"
        checksum = hashlib.sha256(checksum_src.encode("utf-8")).hexdigest()

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                KITE_TOKEN_URL,
                headers={
                    "X-Kite-Version": "3",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "api_key": settings.kite_api_key,
                    "request_token": request_token,
                    "checksum": checksum,
                },
            )
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data") if isinstance(payload, dict) else {}
        access_token = data.get("access_token") if isinstance(data, dict) else None
        if not access_token:
            raise ValueError(f"No access_token in Kite response: {payload}")
        return str(access_token)

    async def validate_token(self, token: str) -> bool:
        if not token:
            return False

        now = time.monotonic()
        cached = self._token_validation_cache.get(token)
        if cached and cached[0] > now:
            return cached[1]

        is_valid = await self._request_profile(token) is not None
        self._token_validation_cache[token] = (now + 30.0, is_valid)
        return is_valid

    async def fetch_account_info(self, token: str) -> BrokerAccountInfo | None:
        profile_payload = await self._request_profile(token)
        if profile_payload is None:
            return None

        data = profile_payload.get("data") if isinstance(profile_payload, dict) else {}
        if not isinstance(data, dict):
            data = {}

        account_id = data.get("user_id") or data.get("user_shortname")
        account_owner = data.get("user_name") or data.get("user_shortname")
        account_label = data.get("user_shortname") or data.get("email") or account_id

        return BrokerAccountInfo(
            account_id=str(account_id) if account_id else None,
            account_label=str(account_label) if account_label else None,
            account_owner=str(account_owner) if account_owner else None,
            raw_profile=profile_payload if isinstance(profile_payload, dict) else None,
        )

    async def _request_profile(self, token: str) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    KITE_PROFILE_URL,
                    headers={
                        "X-Kite-Version": "3",
                        "Authorization": f"token {settings.kite_api_key}:{token}",
                        "Accept": "application/json",
                    },
                )
        except Exception as exc:
            logger.warning("Kite profile request failed: %s", exc)
            return None

        if response.status_code in {401, 403}:
            return None
        if response.status_code >= 400:
            logger.warning(
                "Kite profile request failed with status=%s",
                response.status_code,
            )
            return None

        payload = response.json()
        if isinstance(payload, dict) and payload.get("status") == "error":
            return None
        return payload if isinstance(payload, dict) else None
