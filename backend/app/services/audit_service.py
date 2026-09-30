"""
app/services/audit_service.py
---------------------------------
Generic "who did what, when" audit trail, separate from a complaint's own
timeline (ComplaintEvent). Call log() from any admin action worth
recording; never raises (a logging failure should not break the action
it's logging).
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.repository import audit_repository


def log(db: Session, actor: str, action: str, target_type: Optional[str] = None,
        target_id: Optional[str] = None, details: Optional[str] = None) -> None:
    try:
        audit_repository.add(db, actor=actor, action=action, target_type=target_type,
                              target_id=target_id, details=details)
    except Exception as e:  # noqa: BLE001 — audit logging must never break the caller
        print(f"[audit] failed to log {action} by {actor}: {e}")


def list_logs(db: Session, actor: Optional[str], action: Optional[str], target_type: Optional[str],
              date_from: Optional[str], date_to: Optional[str], limit: int, offset: int) -> dict:
    total, items = audit_repository.search(
        db, actor=actor, action=action, target_type=target_type,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": [r.to_dict() for r in items]}
