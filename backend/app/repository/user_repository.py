"""app/repository/user_repository.py"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User


def get_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def create(db: Session, username: str, password_hash: str, role: str, email: Optional[str] = None) -> User:
    u = User(username=username, password_hash=password_hash, role=role, email=email)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def update_email(db: Session, user: User, email: Optional[str]) -> User:
    user.email = email
    db.commit()
    db.refresh(user)
    return user
