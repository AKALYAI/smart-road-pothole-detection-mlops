"""
app/models/complaint_event.py
------------------------------
Audit trail / timeline for a complaint: created, assigned, status changes,
duplicate reports merged in, repair photo uploaded... This is what the
citizen "Track complaint" timeline renders.
"""
from sqlalchemy import Column, DateTime, Integer, String

from app.db.session import Base
from app.utils.timeutil import utcnow


class ComplaintEvent(Base):
    __tablename__ = "complaint_events"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)  # created|assigned|status_changed|duplicate_report|repair_photo|reopened
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)
    note = Column(String, nullable=True)
    actor = Column(String, nullable=True)        # username, or "system"
    created_at = Column(DateTime, default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "complaint_id": self.complaint_id,
            "event_type": self.event_type,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "note": self.note,
            "actor": self.actor,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
