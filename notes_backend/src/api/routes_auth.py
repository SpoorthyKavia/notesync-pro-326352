from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.api.deps import AuthenticatedUser, get_current_user
from src.api.schemas import AuthResponse, LoginRequest, MeResponse, SignupRequest
from src.core.settings import settings
from src.db.repo import Repo
from src.db.session import get_db_session
from src.security.passwords import hash_password, verify_password
from src.security.tokens import create_access_token, new_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create account",
    description="Create a user account with email + password and return an access token.",
)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db_session)) -> AuthResponse:
    repo = Repo(db)
    existing = await repo.get_user_by_email(payload.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = await repo.create_user(email=payload.email, password_hash=hash_password(payload.password))

    session_token = new_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.access_token_ttl_seconds)
    await repo.create_session(user_id=user.id, session_token=session_token, expires_at=expires_at)

    token = create_access_token(user_id=user.id, session_token=session_token)
    return AuthResponse(access_token=token.token, expires_at=token.expires_at)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login",
    description="Authenticate with email + password, create a server session, and return an access token.",
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db_session)) -> AuthResponse:
    repo = Repo(db)
    user = await repo.get_user_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    session_token = new_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.access_token_ttl_seconds)
    await repo.create_session(user_id=user.id, session_token=session_token, expires_at=expires_at)

    token = create_access_token(user_id=user.id, session_token=session_token)
    return AuthResponse(access_token=token.token, expires_at=token.expires_at)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Current user",
    description="Return the currently authenticated user's profile.",
)
async def me(user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> MeResponse:
    repo = Repo(db)
    row = await repo.get_user_by_id(user.user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return MeResponse(id=row.id, email=row.email, created_at=row.created_at)
