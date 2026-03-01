from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase
from typing import Any


class UserChart(Base, PrimaryKeyModel, TimeStampMixin):
    __tablename__ = "user_charts"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    symbol: Mapped[str | None] = mapped_column(nullable=True)
    resolution: Mapped[str | None] = mapped_column(nullable=True)
    content: Mapped[dict] = mapped_column(JSONB)


class UserStudyTemplate(Base, PrimaryKeyModel, TimeStampMixin):
    __tablename__ = "user_study_templates"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_study_templates_user_name"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    content: Mapped[dict] = mapped_column(JSONB)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────


class ChartCreate(TerminalBase):
    name: str
    symbol: str | None = None
    resolution: str | None = None
    content: dict


class ChartUpdate(TerminalBase):
    name: str | None = None
    symbol: str | None = None
    resolution: str | None = None
    content: dict | None = None


class ChartMeta(TerminalBase):
    id: str
    name: str
    symbol: str | None = None
    resolution: str | None = None


class ChartPublic(ChartMeta):
    content: Any


class StudyTemplateCreate(TerminalBase):
    name: str
    content: dict


class StudyTemplateMeta(TerminalBase):
    name: str
