from datetime import datetime, timezone
from typing import Generic, TypeVar, List, ClassVar
from sqlmodel import SQLModel, Field, DateTime
from pydantic import ConfigDict, BaseModel
from uuid import uuid7


def uuid7_str() -> str:
    return str(uuid7())


class TerminalBase(BaseModel):
    """Base Pydantic model with shared config for Terminal models."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        json_encoders={
            # custom output conversion for datetime
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if v else None,
        },
    )


class TimeStampMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
    )


class PrimaryKeyModel(SQLModel):
    id: str = Field(
        default_factory=uuid7_str,
        primary_key=True,
    )


T = TypeVar("T")


class Pagination(TerminalBase, Generic[T]):
    items: List[T]
    itemsPerPage: int
    total: int
    page: int
