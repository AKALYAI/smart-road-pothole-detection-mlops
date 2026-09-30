"""app/repository/alert_repository.py"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.alert import Alert


def create(db: Session, complaint_id: str, severity: str, message: str) -> Alert:
    a = Alert(complaint_id=complaint_id, severity=severity, message=message, acknowledged=False)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def list_alerts(db: Session, unread_only: bool = False, limit: int = 100) -> List[Alert]:
    q = db.query(Alert)
    if unread_only:
        q = q.filter(Alert.acknowledged.is_(False))
    return q.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit).all()


def unread_count(db: Session) -> int:
    return db.query(Alert).filter(Alert.acknowledged.is_(False)).count()


def get(db: Session, alert_id: int) -> Optional[Alert]:
    return db.query(Alert).filter(Alert.id == alert_id).first()


def acknowledge(db: Session, alert: Alert, actor: str) -> Alert:
    alert.acknowledged = True
    alert.acknowledged_by = actor
    db.commit()
    db.refresh(alert)
    return alert


def acknowledge_all(db: Session, actor: str) -> int:
    n = (
        db.query(Alert)
        .filter(Alert.acknowledged.is_(False))
        .update({"acknowledged": True, "acknowledged_by": actor}, synchronize_session=False)
    )
    db.commit()
    return n
