import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.broker import service as broker_service
from terminal.broker.adapter import Capability, Market
from terminal.broker.feed_registry import feed_registry
from terminal.broker.models import (
    BrokerAccount,
    BrokerCredential,
    BrokerDefaultPayload,
    BrokerInfo,
    BrokerStatus,
)
from terminal.broker.registry import broker_registry
from terminal.dependencies import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker", tags=["Broker"])


class CallbackRequest(BaseModel):
    code: str


class SetDefaultRequest(BaseModel):
    capability: str
    market: str
    provider_id: str


def _get_provider(provider_id: str):
    adapter = broker_registry.get(provider_id)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown broker provider: {provider_id}",
        )
    if not adapter.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Broker provider {provider_id} is not configured on this server",
        )
    return adapter


async def _get_active_valid_credential(
    session: Session,
    user_id: str,
    adapter,
) -> tuple[BrokerCredential | None, str | None]:
    credentials = broker_service.list_provider_credentials(
        session,
        user_id,
        adapter.provider_id,
    )
    for credential in credentials:
        token = broker_service.get_credential_token(credential)
        if token and await adapter.validate_token(token):
            return credential, token
    return None, None


async def _backfill_account_profile_if_needed(
    credential: BrokerCredential,
    adapter,
) -> bool:
    if credential.account_owner and credential.account_label and credential.account_id:
        return False

    token = broker_service.get_credential_token(credential)
    if not token:
        return False

    info = await adapter.fetch_account_info(token)
    if info is None:
        return False

    credential.account_id = info.account_id or credential.account_id
    credential.account_label = info.account_label or credential.account_label
    credential.account_owner = info.account_owner or credential.account_owner
    credential.profile_raw = info.raw_profile or credential.profile_raw
    return True


@router.get("", response_model=list[BrokerInfo])
async def list_brokers(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[BrokerInfo]:
    brokers: list[BrokerInfo] = []
    for adapter in broker_registry.configured():
        accounts = broker_service.list_provider_accounts(
            session,
            current_user.id,
            adapter.provider_id,
        )

        changed = False
        for account in accounts:
            changed = await _backfill_account_profile_if_needed(account, adapter) or changed
        if changed:
            session.commit()
            accounts = broker_service.list_provider_accounts(
                session,
                current_user.id,
                adapter.provider_id,
            )

        active_credential, _ = await _get_active_valid_credential(
            session,
            current_user.id,
            adapter,
        )
        account_items = [
            BrokerAccount(
                account_key=broker_service.credential_account_key(account),
                credential_id=account.id,
                account_id=account.account_id,
                account_label=account.account_label,
                account_owner=account.account_owner,
            )
            for account in accounts
        ]

        token_is_valid = active_credential is not None
        brokers.append(
            BrokerInfo(
                provider_id=adapter.provider_id,
                display_name=adapter.display_name,
                markets=[market.value for market in adapter.markets],
                capabilities=[capability.value for capability in adapter.capabilities],
                connected=token_is_valid,
                login_required=not token_is_valid,
                accounts=account_items,
                active_account_key=(
                    broker_service.credential_account_key(active_credential)
                    if active_credential is not None
                    else None
                ),
            )
        )
    return brokers


@router.get("/defaults", response_model=list[BrokerDefaultPayload])
async def list_defaults(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[BrokerDefaultPayload]:
    rows = broker_service.list_defaults(session, current_user.id)
    return [
        BrokerDefaultPayload(
            capability=row.capability,
            market=row.market,
            provider_id=row.provider_id,
        )
        for row in rows
    ]


@router.put("/defaults", response_model=BrokerDefaultPayload)
async def set_default_broker(
    body: SetDefaultRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrokerDefaultPayload:
    try:
        capability = Capability(body.capability)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported capability: {body.capability}",
        )

    try:
        market = Market(body.market)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported market: {body.market}",
        )

    adapter = _get_provider(body.provider_id)
    if not adapter.supports(capability=capability, market=market):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Broker {body.provider_id} does not support "
                f"capability={capability.value} for market={market.value}"
            ),
        )

    saved = broker_service.save_default(
        session,
        user_id=current_user.id,
        capability=capability.value,
        market=market.value,
        provider_id=body.provider_id,
    )

    return BrokerDefaultPayload(
        capability=saved.capability,
        market=saved.market,
        provider_id=saved.provider_id,
    )


@router.get("/{provider_id}/auth-url")
async def get_provider_auth_url(
    provider_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    adapter = _get_provider(provider_id)
    return {"url": adapter.build_auth_url()}


@router.post("/{provider_id}/callback")
async def provider_callback(
    provider_id: str,
    body: CallbackRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    adapter = _get_provider(provider_id)

    try:
        access_token = await adapter.exchange_code(body.code)
    except Exception as exc:
        logger.error("%s token exchange failed: %s", provider_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {exc}",
        )

    account_info = await adapter.fetch_account_info(access_token)

    broker_service.save_token(
        session,
        current_user.id,
        provider_id,
        access_token,
        account_id=account_info.account_id if account_info else None,
        account_label=account_info.account_label if account_info else None,
        account_owner=account_info.account_owner if account_info else None,
        profile_raw=account_info.raw_profile if account_info else None,
    )
    logger.info("Saved %s token for user=%s", provider_id, current_user.id)

    await feed_registry.update_token(current_user.id, provider_id, access_token)

    from terminal.realtime.handler import connection_manager

    for ws_session in connection_manager.get_sessions(current_user.id):
        try:
            await ws_session.restart_broker_feed(provider_id, access_token)
        except Exception:
            logger.exception(
                "Failed to restart %s feed for session user=%s",
                provider_id,
                current_user.id,
            )

    return {"status": "success"}


@router.delete("/{provider_id}/accounts/{credential_id}")
async def delete_provider_account(
    provider_id: str,
    credential_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    adapter = _get_provider(provider_id)
    credential = broker_service.get_credential(
        session,
        credential_id=credential_id,
        user_id=current_user.id,
        provider=provider_id,
    )
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Broker account not found for credential={credential_id}",
        )

    active_before, _ = await _get_active_valid_credential(
        session,
        current_user.id,
        adapter,
    )

    session.delete(credential)
    session.commit()

    if active_before and active_before.id == credential_id:
        next_active, next_token = await _get_active_valid_credential(
            session,
            current_user.id,
            adapter,
        )
        from terminal.realtime.handler import connection_manager

        if next_active is not None and next_token is not None:
            await feed_registry.update_token(current_user.id, provider_id, next_token)
            for ws_session in connection_manager.get_sessions(current_user.id):
                try:
                    await ws_session.restart_broker_feed(provider_id, next_token)
                except Exception:
                    logger.exception(
                        "Failed to restart %s after account delete for user=%s",
                        provider_id,
                        current_user.id,
                    )
        else:
            await feed_registry.drop(current_user.id, provider_id)
            for ws_session in connection_manager.get_sessions(current_user.id):
                try:
                    await ws_session.broker_disconnected(provider_id)
                except Exception:
                    logger.exception(
                        "Failed to disconnect %s after account delete for user=%s",
                        provider_id,
                        current_user.id,
                    )

    return {"status": "success"}


@router.get("/{provider_id}/status", response_model=BrokerStatus)
async def get_provider_status(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrokerStatus:
    adapter = _get_provider(provider_id)
    active_credential, _ = await _get_active_valid_credential(
        session,
        current_user.id,
        adapter,
    )
    token_is_valid = active_credential is not None
    return BrokerStatus(
        provider_id=provider_id,
        connected=token_is_valid,
        login_required=not token_is_valid,
    )
