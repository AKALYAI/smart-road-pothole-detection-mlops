"""
app/routers/auth_router.py
-----------------------------
POST /auth/register   — create a citizen account
POST /auth/login      — get a JWT (citizen or admin)
GET  /auth/me          — who am I
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_user
from app.db.session import get_db
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6)
    email: Optional[str] = Field(None, description="Optional — used for complaint status-change notifications")


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    user = auth_service.register_citizen(db, body.username, body.password, email=body.email)
    return auth_service.token_response(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    token = auth_service.login(db, body.username, body.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return token


@router.get("/me")
def me(user: CurrentUser = Depends(require_user)):
    return {"username": user.username, "role": user.role}


@router.patch("/me/email")
def update_email(email: Optional[str] = None, user: CurrentUser = Depends(require_user), db: Session = Depends(get_db)):
    """Set/clear the notification email on the logged-in account."""
    from app.repository import user_repository
    from app.services.auth_service import _EMAIL_RE
    if email and not _EMAIL_RE.match(email):
        raise HTTPException(400, "That doesn't look like a valid email address.")
    u = user_repository.get_by_username(db, user.username)
    u = user_repository.update_email(db, u, email)
    return u.to_dict()
