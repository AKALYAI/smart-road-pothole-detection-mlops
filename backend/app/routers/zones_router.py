"""
app/routers/zones_router.py
--------------------------------
Multi-zone management + Road Health Score.

GET    /zones            — all zones with health score, worst-health first  [public]
POST   /zones             — create a zone                                    [admin]
GET    /zones/{id}        — zone detail: health breakdown + its complaints    [public]
DELETE /zones/{id}        — delete a zone (complaints keep their zone_id,     [admin]
                             they just won't match a zone lookup any more)

A complaint is auto-assigned to the nearest zone that contains it (see
app/services/zone_service.find_zone_for, called from complaint_service)
at the time it's filed — creating a zone later does not retroactively
re-tag old complaints.
"""
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin
from app.db.session import get_db
from app.repository import zone_repository
from app.services import audit_service, zone_service

router = APIRouter(prefix="/zones", tags=["Zones"])


def _get_zone_or_404(db: Session, zone_id: int):
    zone = zone_repository.get(db, zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    return zone


@router.get("")
def list_zones(db: Session = Depends(get_db)):
    return {"zones": zone_service.list_zones_with_health(db)}


@router.post("")
def create_zone(
    name: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    radius_km: float = Form(2.0),
    description: str = Form(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    zone = zone_service.create_zone(db, name, latitude, longitude, radius_km, description, user.username)
    audit_service.log(db, user.username, "zone_created", "zone", str(zone.id), f"{name} (r={radius_km}km)")
    return zone.to_dict()


@router.get("/{zone_id}")
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    zone = _get_zone_or_404(db, zone_id)
    return zone_service.zone_detail(db, zone)


@router.delete("/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    zone = _get_zone_or_404(db, zone_id)
    zone_service.delete_zone(db, zone)
    audit_service.log(db, user.username, "zone_deleted", "zone", str(zone_id), zone.name)
    return {"deleted": zone_id}
