from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict
from uuid import uuid4

import jwt

from src.core.settings import settings


@dataclass(frozen=True)
class AccessToken:
    """
    Access token result.

    Contract:
    - token: JWT string.
    - expires_at: unix timestamp seconds.
    - session_token: opaque token persisted in DB sessions table.
    """

    token: str
    expires_at: int
    session_token: str


# PUBLIC_INTERFACE
def create_access_token(*, user_id: str, session_token: str) -> AccessToken:
    """Create a signed JWT access token for the given user and session."""
    now = int(time.time())
    exp = now + settings.access_token_ttl_seconds
    payload: Dict[str, Any] = {
        "iss": settings.auth_jwt_issuer,
        "sub": user_id,
        "iat": now,
        "exp": exp,
        "sid": session_token,
    }
    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")
    return AccessToken(token=token, expires_at=exp, session_token=session_token)


# PUBLIC_INTERFACE
def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
      jwt.InvalidTokenError if token is invalid/expired.
    """
    return jwt.decode(
        token,
        settings.auth_jwt_secret,
        algorithms=["HS256"],
        issuer=settings.auth_jwt_issuer,
        options={"require": ["iss", "sub", "exp", "iat"]},
    )


# PUBLIC_INTERFACE
def new_session_token() -> str:
    """Generate a new opaque session token."""
    return uuid4().hex
