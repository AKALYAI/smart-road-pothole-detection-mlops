"""
app/routers/insights_router.py
-----------------------------------
GET /insights            — dashboard summary stats (severity/status/department, resolution time)  [admin]
GET /insights/map         — geotagged complaint markers + heatmap points                            [public]
GET /insights/trends       — daily/weekly/monthly complaint counts                                  [admin]
GET /insights/confidence   — model confidence distribution + review queue                            [admin]
GET /insights/hotspots     — grid-clustered pothole-prone areas                                      [admin]
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin
from app.db.session import get_db
from app.services import insights_service

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("")
def insights(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return insights_service.get_insights(db)


@router.get("/map")
def map_data(include_resolved: bool = Query(True), db: Session = Depends(get_db)):
    return insights_service.get_map_data(db, include_resolved=include_resolved)


@router.get("/trends")
def trends(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    periods: Optional[int] = Query(None, ge=1, le=180),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    return insights_service.get_trends(db, period=period, periods=periods)


@router.get("/confidence")
def confidence(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return insights_service.get_confidence(db)


@router.get("/hotspots")
def hotspots(top: int = Query(10, ge=1, le=50), db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return insights_service.get_hotspots(db, top=top)
