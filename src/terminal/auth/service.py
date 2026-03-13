from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from terminal.auth.models import User, UserCreate
from terminal.config import settings


def verify_token(token: str) -> str | None:
    """Decode a JWT and return the ``sub`` claim, or ``None`` if invalid."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


async def get(session: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID."""
    return await session.get(User, user_id)


async def get_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """Get user by username."""
    statement = select(User).where(User.username == username)
    return (await session.execute(statement)).scalars().first()


async def create(session: AsyncSession, user_in: UserCreate) -> Optional[User]:
    """Register a new user from a UserCreate schema."""
    user = await get_by_username(session, user_in.username)
    if user:
        return None

    new_user = User(username=user_in.username, hashed_password="")
    new_user.set_password(user_in.password)
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def authenticate(session: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authenticate a user and return the user object or None."""
    user = await get_by_username(session, username)
    if not user or not user.verify_password(password):
        return None
    return user
