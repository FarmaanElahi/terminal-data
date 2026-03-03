from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Text, UniqueConstraint, JSON
from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase


class BrokerCredential(Base, PrimaryKeyModel, TimeStampMixin):
    __tablename__ = "broker_credentials"
    # No unique constraint — multiple credentials per (user, provider) allowed.
    # Most recently created is used.

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(index=True)  # e.g. "upstox"
    account_id: Mapped[str | None] = mapped_column(index=True, nullable=True)
    account_label: Mapped[str | None] = mapped_column(nullable=True)
    account_owner: Mapped[str | None] = mapped_column(nullable=True)
    profile_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    encrypted_token: Mapped[str] = mapped_column(Text)


class BrokerDefault(Base, PrimaryKeyModel, TimeStampMixin):
    __tablename__ = "broker_defaults"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "capability",
            "market",
            name="uq_broker_defaults_user_capability_market",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    capability: Mapped[str] = mapped_column(index=True)  # e.g. "realtime_candles"
    market: Mapped[str] = mapped_column(index=True)  # e.g. "india"
    provider_id: Mapped[str] = mapped_column(index=True)  # e.g. "upstox"


class BrokerStatus(TerminalBase):
    provider_id: str
    connected: bool
    login_required: bool


class BrokerInfo(BrokerStatus):
    display_name: str
    markets: list[str]
    capabilities: list[str]
    accounts: list["BrokerAccount"]
    active_account_key: str | None = None


class BrokerAccount(TerminalBase):
    account_key: str
    credential_id: str
    account_id: str | None = None
    account_label: str | None = None
    account_owner: str | None = None


class BrokerDefaultPayload(TerminalBase):
    capability: str
    market: str
    provider_id: str
