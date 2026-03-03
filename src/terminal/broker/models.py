from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Text
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
    encrypted_token: Mapped[str] = mapped_column(Text)


class BrokerStatus(TerminalBase):
    connected: bool
    login_required: bool
    provider: str
