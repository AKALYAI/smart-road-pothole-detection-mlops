"""app/models/user.py — login accounts. role: "admin" | "citizen"."""
from sqlalchemy import Column, DateTime, Integer, String

from app.db.session import Base
from app.utils.timeutil import utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="citizen")
    email = Column(String, nullable=True)  # optional — used for status-change notifications
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {"username": self.username, "role": self.role, "email": self.email}
