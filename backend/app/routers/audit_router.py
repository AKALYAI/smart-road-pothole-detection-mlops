"""
app/routers/audit_router.py
--------------------------------
GET /audit — searchable audit trail of admin actions (who did what, when).
Complaint-specific history lives on the complaint itself (GET
/complaints/{id} -> events); this is the cross-cutting log: logins, zone
management, dataset uploads, corrections, department assignment, status
changes, alert acknowledgement, etc.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin
from app.db.session import get_db
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
def list_audit_logs(
    actor: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    return audit_service.list_logs(db, actor, action, target_type, date_from, date_to, limit, offset)
