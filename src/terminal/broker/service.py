from sqlalchemy import select
from sqlalchemy.orm import Session

from terminal.broker.models import BrokerCredential, BrokerDefault
from terminal.lib.crypto import decrypt, encrypt
from terminal.models import uuid7_str


def get_active_token(session: Session, user_id: str, provider: str) -> str | None:
    """Return the plaintext access token for the most recently created credential."""
    cred = get_active_credential(session, user_id, provider)
    if cred is None:
        return None
    try:
        return decrypt(cred.encrypted_token)
    except Exception:
        return None


def save_token(
    session: Session,
    user_id: str,
    provider: str,
    token: str,
    *,
    account_id: str | None = None,
    account_label: str | None = None,
    account_owner: str | None = None,
    profile_raw: dict | None = None,
) -> BrokerCredential:
    """Insert a new encrypted credential row (multiple rows per user+provider allowed)."""
    cred = BrokerCredential(
        id=uuid7_str(),
        user_id=user_id,
        provider=provider,
        account_id=account_id,
        account_label=account_label,
        account_owner=account_owner,
        profile_raw=profile_raw,
        encrypted_token=encrypt(token),
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return cred


def credential_account_key(cred: BrokerCredential) -> str:
    return cred.account_id or f"cred:{cred.id}"


def get_active_credential(
    session: Session,
    user_id: str,
    provider: str,
) -> BrokerCredential | None:
    return session.execute(
        select(BrokerCredential)
        .where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.provider == provider,
        )
        .order_by(BrokerCredential.created_at.desc())
        .limit(1)
    ).scalars().first()


def list_provider_accounts(
    session: Session,
    user_id: str,
    provider: str,
) -> list[BrokerCredential]:
    """Return latest credential per account for this provider."""
    rows = list(
        session.execute(
            select(BrokerCredential)
            .where(
                BrokerCredential.user_id == user_id,
                BrokerCredential.provider == provider,
            )
            .order_by(BrokerCredential.created_at.desc())
        ).scalars()
    )

    seen: set[str] = set()
    latest_accounts: list[BrokerCredential] = []
    for row in rows:
        key = credential_account_key(row)
        if key in seen:
            continue
        seen.add(key)
        latest_accounts.append(row)

    return latest_accounts


def list_provider_credentials(
    session: Session,
    user_id: str,
    provider: str,
) -> list[BrokerCredential]:
    return list(
        session.execute(
            select(BrokerCredential)
            .where(
                BrokerCredential.user_id == user_id,
                BrokerCredential.provider == provider,
            )
            .order_by(BrokerCredential.created_at.desc())
        ).scalars()
    )


def get_credential_token(credential: BrokerCredential) -> str | None:
    try:
        return decrypt(credential.encrypted_token)
    except Exception:
        return None


def get_credential(
    session: Session,
    credential_id: str,
    user_id: str,
    provider: str,
) -> BrokerCredential | None:
    return session.execute(
        select(BrokerCredential).where(
            BrokerCredential.id == credential_id,
            BrokerCredential.user_id == user_id,
            BrokerCredential.provider == provider,
        )
    ).scalars().first()


def get_default_provider(
    session: Session,
    user_id: str,
    capability: str,
    market: str,
) -> str | None:
    row = session.execute(
        select(BrokerDefault.provider_id).where(
            BrokerDefault.user_id == user_id,
            BrokerDefault.capability == capability,
            BrokerDefault.market == market,
        )
    ).scalar_one_or_none()
    return row


def get_defaults_map(session: Session, user_id: str) -> dict[tuple[str, str], str]:
    rows = session.execute(
        select(BrokerDefault).where(BrokerDefault.user_id == user_id)
    ).scalars()
    return {(row.capability, row.market): row.provider_id for row in rows}


def list_defaults(session: Session, user_id: str) -> list[BrokerDefault]:
    return list(
        session.execute(
            select(BrokerDefault).where(BrokerDefault.user_id == user_id)
        ).scalars()
    )


def save_default(
    session: Session,
    user_id: str,
    capability: str,
    market: str,
    provider_id: str,
) -> BrokerDefault:
    existing = session.execute(
        select(BrokerDefault).where(
            BrokerDefault.user_id == user_id,
            BrokerDefault.capability == capability,
            BrokerDefault.market == market,
        )
    ).scalars().first()

    if existing is None:
        existing = BrokerDefault(
            id=uuid7_str(),
            user_id=user_id,
            capability=capability,
            market=market,
            provider_id=provider_id,
        )
        session.add(existing)
    else:
        existing.provider_id = provider_id

    session.commit()
    session.refresh(existing)
    return existing
