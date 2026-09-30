"""
app/repository/complaint_repository.py
-----------------------------------------
All raw DB queries for the `Complaint` entity live here, and nowhere
else — services call into this module instead of touching `db.query(...)`
directly.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.utils.geo import bounding_box, haversine_m


def create(db: Session, complaint: Complaint) -> Complaint:
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


def save(db: Session, complaint: Complaint) -> Complaint:
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


def get_by_complaint_id(db: Session, complaint_id: str) -> Optional[Complaint]:
    return db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()


def list_all(db: Session) -> List[Complaint]:
    return db.query(Complaint).order_by(Complaint.date_reported.desc()).all()


_SORT_COLUMNS = {
    "date_reported": Complaint.date_reported,
    "severity": Complaint.severity,
    "status": Complaint.status,
    "confidence": Complaint.confidence,
    "num_potholes": Complaint.num_potholes,
}


def search(
    db: Session,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    reporter: Optional[str] = None,
    zone_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search_text: Optional[str] = None,
    sort_by: str = "date_reported",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(Complaint)
    if severity:
        # supports a single value ("High") or a comma-separated list ("High,Critical")
        # for Advanced Search & Filters' multi-select severity.
        values = [v.strip() for v in severity.split(",") if v.strip()]
        q = q.filter(Complaint.severity.in_(values)) if len(values) > 1 else q.filter(Complaint.severity == values[0])
    if status:
        q = q.filter(Complaint.status == status)
    if department:
        q = q.filter(Complaint.department == department)
    if reporter:
        q = q.filter(Complaint.reporter == reporter)
    if zone_id is not None:
        q = q.filter(Complaint.zone_id == zone_id)
    if date_from:
        q = q.filter(Complaint.date_reported >= date_from)
    if date_to:
        q = q.filter(Complaint.date_reported <= date_to)
    if search_text:
        like = f"%{search_text}%"
        q = q.filter((Complaint.complaint_id.ilike(like)) | (Complaint.address.ilike(like)))

    total = q.count()
    col = _SORT_COLUMNS.get(sort_by, Complaint.date_reported)
    col = col.desc() if sort_order == "desc" else col.asc()
    items = q.order_by(col).offset(offset).limit(limit).all()
    return total, items


def find_unresolved_near(
    db: Session, lat: float, lng: float, radius_m: float
) -> List[Tuple[Complaint, float]]:
    """Unresolved complaints within radius_m of (lat, lng), nearest first.
    Uses a bounding-box SQL pre-filter, then exact haversine distance."""
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_m)
    candidates = (
        db.query(Complaint)
        .filter(Complaint.status != "Resolved")
        .filter(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None))
        .filter(Complaint.latitude.between(min_lat, max_lat))
        .filter(Complaint.longitude.between(min_lng, max_lng))
        .all()
    )
    hits = []
    for c in candidates:
        d = haversine_m(lat, lng, c.latitude, c.longitude)
        if d <= radius_m:
            hits.append((c, d))
    hits.sort(key=lambda t: t[1])
    return hits


def list_unresolved_with_hash(db: Session, limit: int = 1000) -> List[Complaint]:
    return (
        db.query(Complaint)
        .filter(Complaint.status != "Resolved")
        .filter(Complaint.image_hash.isnot(None))
        .order_by(Complaint.date_reported.desc())
        .limit(limit)
        .all()
    )


def list_by_zone(db: Session, zone_id: int) -> List[Complaint]:
    return db.query(Complaint).filter(Complaint.zone_id == zone_id).all()


def delete(db: Session, complaint: Complaint) -> None:
    db.delete(complaint)
    db.commit()
