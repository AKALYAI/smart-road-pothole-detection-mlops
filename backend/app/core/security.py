"""
app/core/security.py
---------------------
Two layers of auth:

1. `verify_api_key`  — shared X-API-Key guarding the prediction endpoints
   (the dashboard sends it automatically).
2. JWT bearer tokens — real user accounts. `require_admin` protects the
   admin-only endpoints (assign, change status, analytics, alerts...);
   `get_current_user_optional` lets /predict tag a report with the citizen
   who filed it when they are logged in (anonymous reports still work).
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.core.config import settings
from app.core.tokens import decode_access_token


@dataclass
class CurrentUser:
    username: str
    role: str


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """FastAPI dependency: raises 401 if the request is missing/using the
    wrong X-API-Key header (unless auth has been disabled via config)."""
    if not settings.REQUIRE_API_KEY:
        return True
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")
    return True


def _parse_bearer(authorization: Optional[str]) -> Optional[CurrentUser]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    payload = decode_access_token(authorization[7:].strip())
    if not payload or "sub" not in payload:
        return None
    return CurrentUser(username=payload["sub"], role=payload.get("role", "citizen"))


def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[CurrentUser]:
    return _parse_bearer(authorization)


def require_user(user: Optional[CurrentUser] = Depends(get_current_user_optional)) -> CurrentUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Login required.")
    return user


def require_admin(user: CurrentUser = Depends(require_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
