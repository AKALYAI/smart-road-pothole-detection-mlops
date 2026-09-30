"""
app/services/insights_service.py
-------------------------------------
Aggregates complaint records into what the dashboards need:

  get_insights()   severity / status / department breakdowns, resolution time
  get_map_data()   public map markers + heatmap points
  get_trends()     daily / weekly / monthly counts (split by severity)
  get_confidence() model confidence & detection-quality analysis
  get_hotspots()   grid-clustered "pothole-prone areas"
"""
import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.constants import CONF_MEDIUM, DEPARTMENTS, SEVERITY_WEIGHT, STATUSES
from app.repository import complaint_repository
from app.services import analytics


def get_insights(db: Session) -> dict:
    complaints = complaint_repository.list_all(db)
    by_severity = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    by_status = {s: 0 for s in STATUSES}
    by_department = {d: 0 for d in DEPARTMENTS}
    unassigned = 0
    resolution_hours = []
    duplicates_merged = 0
    geotagged = 0
    urgent_open = 0

    for c in complaints:
        if c.severity in by_severity:
            by_severity[c.severity] += 1
        if c.status in by_status:
            by_status[c.status] += 1
        if c.department:
            by_department[c.department] = by_department.get(c.department, 0) + 1
        elif c.status != "Resolved":
            unassigned += 1
        if c.resolved_at and c.date_reported:
            resolution_hours.append((c.resolved_at - c.date_reported).total_seconds() / 3600)
        duplicates_merged += max((c.report_count or 1) - 1, 0)
        if c.latitude is not None and c.longitude is not None:
            geotagged += 1
        if c.status != "Resolved" and c.severity in ("High", "Critical"):
            urgent_open += 1

    trend = analytics.trend_series([(c.date_reported, c.severity) for c in complaints], "daily", 14)

    return {
        "total_complaints": len(complaints),
        "by_severity": by_severity,
        "by_status": by_status,
        "by_department": by_department,
        "unassigned_open": unassigned,
        "urgent_open": urgent_open,               # High/Critical still not resolved
        "geotagged": geotagged,
        "duplicates_merged": duplicates_merged,   # repeat reports folded into existing tickets
        "avg_resolution_hours": round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None,
        # kept for backwards compatibility with the v1 dashboard
        "trend": [{"date": p["period"], "count": p["total"]} for p in trend["points"]],
    }


def get_map_data(db: Session, include_resolved: bool = True) -> dict:
    """Public, privacy-safe map data: no reporter, no images."""
    locations, heat = [], []
    for c in complaint_repository.list_all(db):
        if c.latitude is None or c.longitude is None:
            continue
        if not include_resolved and c.status == "Resolved":
            continue
        locations.append({
            "complaint_id": c.complaint_id, "lat": c.latitude, "lng": c.longitude,
            "severity": c.severity, "status": c.status,
            "department": c.department, "report_count": c.report_count or 1,
        })
        # weight: severity, nudged up a little for repeat reports (more people are affected)
        weight = min(SEVERITY_WEIGHT.get(c.severity, 0.25) + 0.1 * ((c.report_count or 1) - 1), 1.0)
        heat.append([c.latitude, c.longitude, round(weight, 2)])
    return {"locations": locations, "heat": heat}


def get_trends(db: Session, period: str = "daily", periods: Optional[int] = None) -> dict:
    complaints = complaint_repository.list_all(db)
    return analytics.trend_series(
        [(c.date_reported, c.severity) for c in complaints], period, periods, today=datetime.date.today()
    )


def get_confidence(db: Session) -> dict:
    complaints = complaint_repository.list_all(db)
    detections = []
    for c in complaints:
        detections.extend(c.detections())
    stats = analytics.confidence_stats(detections)

    # complaints whose WEAKEST detection is low-confidence -> worth a human look
    review = sorted(
        (c for c in complaints if c.min_confidence is not None and c.min_confidence < CONF_MEDIUM
         and c.status != "Resolved"),
        key=lambda c: c.min_confidence,
    )[:10]
    stats["needs_review"] = [
        {"complaint_id": c.complaint_id, "min_confidence": round(c.min_confidence, 3),
         "severity": c.severity, "status": c.status}
        for c in review
    ]
    stats["thresholds"] = {"high": 0.70, "medium": CONF_MEDIUM}
    return stats


def get_hotspots(db: Session, top: int = 10) -> dict:
    pts = [
        {"lat": c.latitude, "lng": c.longitude, "severity": c.severity}
        for c in complaint_repository.list_all(db)
        if c.latitude is not None and c.longitude is not None and c.status != "Resolved"
    ]
    return {"cell_size_m": 550, "hotspots": analytics.hotspots(pts, top=top)}
