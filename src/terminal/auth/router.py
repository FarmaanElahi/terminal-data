from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session
import jwt

from terminal.database import get_session
from terminal.auth.models import User, UserCreate, Token
from terminal.auth import service as auth_service
from terminal.auth.security import create_access_token, SECRET_KEY, ALGORITHM

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
user_router = APIRouter(prefix="/user", tags=["User"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


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
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = auth_service.get_by_username(session, username)
    if user is None:
        raise credentials_exception
    return user


@auth_router.post("/register", response_model=User)
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
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Login and receive a JWT token."""
    from fastapi import HTTPException

    user = auth_service.authenticate(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@user_router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user details."""
    return current_user
