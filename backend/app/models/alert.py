"""app/models/alert.py — High/Critical pothole alerts shown to admins."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.db.session import Base
from app.utils.timeutil import utcnow


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String, index=True, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow, index=True)
    acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_by = Column(String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "complaint_id": self.complaint_id,
            "severity": self.severity,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "acknowledged": bool(self.acknowledged),
            "acknowledged_by": self.acknowledged_by,
        }
