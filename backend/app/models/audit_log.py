"""
app/models/audit_log.py
--------------------------
Generic audit trail: who did what, to what, and when — across the whole
app (not just complaints, which already have their own ComplaintEvent
timeline). Written by app/services/audit_service.py from the routers that
perform admin actions.
"""
from sqlalchemy import Column, DateTime, Integer, String

from app.db.session import Base
from app.utils.timeutil import utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, nullable=False, index=True)     # username, or "system"
    action = Column(String, nullable=False, index=True)     # e.g. "status_changed", "zone_created"
    target_type = Column(String, nullable=True, index=True)  # e.g. "complaint", "zone", "dataset_image"
    target_id = Column(String, nullable=True, index=True)
    details = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "actor": self.actor,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
