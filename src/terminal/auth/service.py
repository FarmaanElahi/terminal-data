from typing import Optional
from sqlmodel import Session, select
from terminal.auth.models import User, UserCreate


def get(session: Session, user_id: str) -> Optional[User]:
    """Get user by ID."""
    return session.get(User, user_id)


def get_by_username(session: Session, username: str) -> Optional[User]:
    """Get user by username."""
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def create(session: Session, user_in: UserCreate) -> Optional[User]:
    """Register a new user from a UserCreate schema."""
    user = get_by_username(session, user_in.username)
    if user:
        return None

    new_user = User(username=user_in.username, hashed_password="")
    new_user.set_password(user_in.password)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user


def authenticate(session: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user and return the user object or None."""
    user = get_by_username(session, username)
    if not user or not user.verify_password(password):
        return None
    return user
