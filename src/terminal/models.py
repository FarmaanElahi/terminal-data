from datetime import datetime, timezone
from typing import Generic, TypeVar, List as TypingList
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime
from pydantic import ConfigDict, BaseModel
from uuid import uuid7


def uuid7_str() -> str:
    return str(uuid7())


class TerminalBase(BaseModel):
    """Base Pydantic model with shared config for Terminal models."""

    model_config: ConfigDict = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        json_encoders={
            # custom output conversion for datetime
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if v else None,
        },
    )


class TimeStampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PrimaryKeyModel:
    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=uuid7_str,
    )


T = TypeVar("T")


class Pagination(TerminalBase, Generic[T]):
    items: TypingList[T]
    itemsPerPage: int
    total: int
    page: int
