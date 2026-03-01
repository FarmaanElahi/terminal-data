from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase
from typing import Any


class UserPreferences(Base, PrimaryKeyModel, TimeStampMixin):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_preferences_user_id"),)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)


class PreferencesPublic(TerminalBase):
    layout: Any | None = None
    settings: Any | None = None


class PreferencesUpdate(TerminalBase):
    layout: Any | None = None
    settings: Any | None = None
