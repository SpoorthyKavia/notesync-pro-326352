from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.db.session import get_db_session
from src.security.tokens import decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str


# PUBLIC_INTERFACE
async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db_session),
) -> AuthenticatedUser:
    """
    Resolve the current user from Authorization: Bearer <token>.

    Contract:
    - Inputs: Authorization header.
    - Outputs: AuthenticatedUser containing user_id.
    - Errors:
      - 401 if missing/invalid token
      - 401 if session has been revoked/expired in DB
    - Side-effects: reads sessions table.
    """
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(payload.get("sub"))
    session_token = str(payload.get("sid"))

    # Enforce session validity in DB (revocation support).
    result = await db.execute(
        text(
            """
            SELECT 1
            FROM sessions
            WHERE user_id = :user_id
              AND session_token = :session_token
              AND revoked_at IS NULL
              AND expires_at > NOW()
            LIMIT 1
            """
        ),
        {"user_id": user_id, "session_token": session_token},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(user_id=user_id)
