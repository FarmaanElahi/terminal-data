from pydantic import field_validator
from sqlalchemy.orm import Mapped, mapped_column
from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase


class User(Base, PrimaryKeyModel, TimeStampMixin):
    """
    User model for authentication.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)

    def verify_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash."""
        from terminal.auth.security import verify_password

        return verify_password(password, self.hashed_password)

    def set_password(self, password: str) -> None:
        """Set a new password for the user."""
        from terminal.auth.security import get_password_hash

        self.hashed_password = get_password_hash(password)


class UserCreate(TerminalBase):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        from terminal.config import settings

        if len(v) < settings.min_password_length:
            raise ValueError(
                f"Password must be at least {settings.min_password_length} characters"
            )
        return v


class UserPublic(TerminalBase):
    id: str
    username: str
    is_active: bool


class Token(TerminalBase):
    access_token: str
    token_type: str
