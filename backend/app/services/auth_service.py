"""
app/services/auth_service.py
------------------------------
Register / authenticate users and seed the default admin account.
"""
import re
from typing import Optional

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_access_token
from app.models.user import User
from app.repository import user_repository

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def ensure_admin(db: Session) -> None:
    """Create the default admin on first start (credentials from env/config)."""
    if user_repository.get_by_username(db, settings.ADMIN_USERNAME) is None:
        user_repository.create(
            db, settings.ADMIN_USERNAME, hash_password(settings.ADMIN_PASSWORD), "admin"
        )
        if settings.ADMIN_PASSWORD == "admin123":
            print("WARNING: default admin account 'admin' / 'admin123' created — "
                  "set ADMIN_PASSWORD before deploying.")


def register_citizen(db: Session, username: str, password: str, email: Optional[str] = None) -> User:
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, "Username must be 3-32 chars: letters, digits, _ . -")
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if email and not _EMAIL_RE.match(email):
        raise HTTPException(400, "That doesn't look like a valid email address.")
    if user_repository.get_by_username(db, username):
        raise HTTPException(409, "That username is already taken.")
    return user_repository.create(db, username, hash_password(password), "citizen", email=email)


def login(db: Session, username: str, password: str) -> Optional[dict]:
    user = user_repository.get_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return token_response(user)


def token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.username, user.role),
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
    }
