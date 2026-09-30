"""
app/services/zone_service.py
--------------------------------
Multi-zone management + Road Health Score.

A Zone is a simple center-point + radius (good enough for a ward, a
highway stretch, or any named area — no GIS server needed). A complaint
is auto-assigned to the nearest zone whose radius contains it (see
assign_zone(), called from complaint_service when a complaint is filed).

Health score (0-100, 100 = perfect):
    100 - sum(weight[severity] for each UNRESOLVED complaint in the zone)
        - (unresolved_ratio * 15)                    # backlog penalty
        - (min(avg_resolution_days, 10) * 1.5)        # slow-resolution penalty
    clamped to [0, 100]
Intentionally simple/interpretable, like the rest of this project's
scoring (severity classifier, drift detection) — easy to explain to a
non-technical stakeholder and easy to tune via ZONE_HEALTH_WEIGHTS.
"""
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.zone import Zone
from app.repository import complaint_repository, zone_repository
from app.utils.geo import haversine_m


def create_zone(db: Session, name: str, latitude: float, longitude: float,
                 radius_km: float, description: Optional[str], created_by: str) -> Zone:
    if zone_repository.get_by_name(db, name):
        raise HTTPException(409, f"A zone named '{name}' already exists.")
    zone = Zone(name=name, latitude=latitude, longitude=longitude,
                radius_km=radius_km, description=description, created_by=created_by)
    return zone_repository.create(db, zone)


def find_zone_for(db: Session, lat: Optional[float], lng: Optional[float]) -> Optional[Zone]:
    """Nearest zone that CONTAINS this point (within its radius), or None."""
    if lat is None or lng is None:
        return None
    best, best_dist = None, None
    for z in zone_repository.list_all(db):
        dist_m = haversine_m(lat, lng, z.latitude, z.longitude)
        if dist_m <= z.radius_km * 1000 and (best_dist is None or dist_m < best_dist):
            best, best_dist = z, dist_m
    return best


def _health_score(complaints: List) -> dict:
    unresolved = [c for c in complaints if c.status != "Resolved"]
    resolved = [c for c in complaints if c.status == "Resolved" and c.resolved_at and c.date_reported]

    penalty = sum(settings.ZONE_HEALTH_WEIGHTS.get(c.severity, 3) for c in unresolved)
    backlog_ratio = len(unresolved) / len(complaints) if complaints else 0
    penalty += backlog_ratio * 15

    avg_resolution_days = None
    if resolved:
        days = [(c.resolved_at - c.date_reported).total_seconds() / 86400 for c in resolved]
        avg_resolution_days = sum(days) / len(days)
        penalty += min(avg_resolution_days, 10) * 1.5

    score = max(0, min(100, round(100 - penalty)))
    return {
        "score": score,
        "total_complaints": len(complaints),
        "unresolved": len(unresolved),
        "resolved": len(resolved),
        "avg_resolution_days": round(avg_resolution_days, 1) if avg_resolution_days is not None else None,
    }


def list_zones_with_health(db: Session) -> List[dict]:
    zones = zone_repository.list_all(db)
    out = []
    for z in zones:
        complaints = complaint_repository.list_by_zone(db, z.id)
        health = _health_score(complaints)
        out.append({**z.to_dict(), **health})
    out.sort(key=lambda z: z["score"])  # worst-health zones first — where attention is needed
    return out


def zone_detail(db: Session, zone: Zone) -> dict:
    complaints = complaint_repository.list_by_zone(db, zone.id)
    health = _health_score(complaints)
    by_severity = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for c in complaints:
        if c.severity in by_severity:
            by_severity[c.severity] += 1
    return {**zone.to_dict(), **health, "by_severity": by_severity,
            "complaints": [c.to_dict(public=True) for c in complaints]}


def delete_zone(db: Session, zone: Zone) -> None:
    zone_repository.delete(db, zone)
