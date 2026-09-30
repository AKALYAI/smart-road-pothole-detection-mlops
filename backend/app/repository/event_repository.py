"""app/repository/event_repository.py — complaint timeline entries."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.complaint_event import ComplaintEvent


def add(
    db: Session,
    complaint_id: str,
    event_type: str,
    actor: str = "system",
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    note: Optional[str] = None,
) -> ComplaintEvent:
    ev = ComplaintEvent(
        complaint_id=complaint_id, event_type=event_type, actor=actor,
        from_status=from_status, to_status=to_status, note=note,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def list_for(db: Session, complaint_id: str) -> List[ComplaintEvent]:
    return (
        db.query(ComplaintEvent)
        .filter(ComplaintEvent.complaint_id == complaint_id)
        .order_by(ComplaintEvent.created_at.asc(), ComplaintEvent.id.asc())
        .all()
    )
