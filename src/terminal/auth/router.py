import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from terminal.dependencies import get_session
from terminal.auth.models import User, UserCreate, Token, UserPublic
from terminal.auth import service as auth_service
from terminal.auth.security import create_access_token

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
user_router = APIRouter(prefix="/users", tags=["Users"])

# Simple in-memory rate limiter for login endpoint
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_LOGIN_RATE_LIMIT = 5  # max attempts
_LOGIN_RATE_WINDOW = 60  # per 60 seconds


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the client is within rate limits."""
    now = time.time()
    attempts = _LOGIN_ATTEMPTS[client_ip]
    # Prune old entries
    _LOGIN_ATTEMPTS[client_ip] = [t for t in attempts if now - t < _LOGIN_RATE_WINDOW]
    return len(_LOGIN_ATTEMPTS[client_ip]) < _LOGIN_RATE_LIMIT


def _record_attempt(client_ip: str) -> None:
    _LOGIN_ATTEMPTS[client_ip].append(time.time())

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    """Dependency to get the current authenticated user."""
    from fastapi import HTTPException

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    username = auth_service.verify_token(token)
    if username is None:
        raise credentials_exception

    user = auth_service.get_by_username(session, username)
    if user is None:
        raise credentials_exception
    return user


@auth_router.post("/register", response_model=UserPublic)
async def register(
    data: UserCreate,
    session: Session = Depends(get_session),
):
    """Register a new user."""
    from fastapi import HTTPException

    user = auth_service.create(session, data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    return user


@auth_router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Login and receive a JWT token."""
    from fastapi import HTTPException

    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    _record_attempt(client_ip)

    user = auth_service.authenticate(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@user_router.get("/me", response_model=UserPublic)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user details."""
    return current_user
