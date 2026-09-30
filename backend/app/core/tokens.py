"""
app/core/tokens.py
-------------------
Create / decode JWT access tokens (PyJWT). Token payload: sub (username),
role ("admin" | "citizen"), exp.
"""
import datetime
from typing import Optional

import jwt

from app.core.config import settings


def create_access_token(username: str, role: str) -> str:
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": username, "role": role, "exp": exp}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Returns the payload, or None if the token is invalid/expired."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
