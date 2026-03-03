import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from terminal.broker.models import BrokerCredential
from terminal.config import settings
from terminal.lib.crypto import decrypt, encrypt
from terminal.models import uuid7_str

UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


def get_active_token(session: Session, user_id: str, provider: str) -> str | None:
    """Return the plaintext access token for the most recently created credential."""
    cred = session.execute(
        select(BrokerCredential)
        .where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.provider == provider,
        )
        .order_by(BrokerCredential.created_at.desc())
        .limit(1)
    ).scalars().first()
    if cred is None:
        return None
    try:
        return decrypt(cred.encrypted_token)
    except Exception:
        return None


def save_token(session: Session, user_id: str, provider: str, token: str) -> BrokerCredential:
    """Insert a new encrypted credential row (multiple rows per user+provider allowed)."""
    cred = BrokerCredential(
        id=uuid7_str(),
        user_id=user_id,
        provider=provider,
        encrypted_token=encrypt(token),
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return cred


async def exchange_upstox_code(code: str) -> str:
    """POST authorization code to Upstox V2 token endpoint and return the access_token."""
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


def build_upstox_auth_url() -> str:
    """Build the Upstox OAuth2 authorization URL."""
    import urllib.parse

    params = urllib.parse.urlencode(
        {
            "client_id": settings.upstox_api_key,
            "redirect_uri": settings.upstox_redirect_uri,
            "response_type": "code",
        }
    )
    return f"https://api.upstox.com/v2/login/authorization/dialog?{params}"
