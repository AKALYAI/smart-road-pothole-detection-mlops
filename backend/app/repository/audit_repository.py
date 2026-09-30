"""app/repository/audit_repository.py"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def add(db: Session, actor: str, action: str, target_type: Optional[str] = None,
        target_id: Optional[str] = None, details: Optional[str] = None) -> AuditLog:
    row = AuditLog(actor=actor, action=action, target_type=target_type, target_id=target_id, details=details)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def search(
    db: Session,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    q = db.query(AuditLog)
    if actor:
        q = q.filter(AuditLog.actor == actor)
    if action:
        q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    if date_from:
        q = q.filter(AuditLog.created_at >= date_from)
    if date_to:
        q = q.filter(AuditLog.created_at <= date_to)
    total = q.count()
    items = q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return total, items
