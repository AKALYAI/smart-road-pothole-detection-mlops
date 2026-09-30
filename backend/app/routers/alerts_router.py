"""
app/routers/alerts_router.py
--------------------------------
GET   /alerts               — list High/Critical pothole alerts        [admin]
GET   /alerts/unread-count    — badge count for the admin bell icon      [admin]
PATCH /alerts/{id}/ack        — acknowledge one alert                    [admin]
PATCH /alerts/ack-all          — acknowledge every unread alert           [admin]
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin
from app.db.session import get_db
from app.repository import alert_repository
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("")
def list_alerts(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    return {"alerts": alert_service.list_alerts(db, unread_only=unread_only)}


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return {"unread": alert_repository.unread_count(db)}


@router.patch("/{alert_id}/ack")
def acknowledge(alert_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    a = alert_repository.get(db, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    return alert_repository.acknowledge(db, a, user.username).to_dict()


@router.patch("/ack-all")
def acknowledge_all(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    n = alert_repository.acknowledge_all(db, user.username)
    return {"acknowledged": n}
