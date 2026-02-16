from sqlmodel import Field
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase


class User(PrimaryKeyModel, TimeStampMixin, table=True):
    """
    User model for authentication.
    """

    username: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)

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


class Token(TerminalBase):
    access_token: str
    token_type: str
