"""
app/services/duplicate_service.py
------------------------------------
Decides whether a new report is really a repeat report of a pothole that
is already open. Two independent signals:

1. LOCATION  — an unresolved complaint within DUPLICATE_RADIUS_M metres
   (haversine distance). Needs GPS on the new report.
2. IMAGE     — the photo's dHash is within DUPLICATE_HASH_DISTANCE bits of
   an unresolved complaint's photo. Catches re-uploads and GPS-less
   reports. If BOTH reports have GPS and are further apart than
   IMAGE_MATCH_MAX_GPS_M, the image match is ignored (different place).

Resolved complaints are never matched, so a pothole that comes back after
repair is filed as a new ticket.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repository import complaint_repository
from app.utils.geo import haversine_m
from app.utils.phash import hamming

IMAGE_MATCH_MAX_GPS_M = 200.0


def find_duplicate(
    db: Session, latitude: Optional[float], longitude: Optional[float], image_hash: Optional[str]
) -> Optional[dict]:
    has_gps = latitude is not None and longitude is not None

    if has_gps:
        hits = complaint_repository.find_unresolved_near(
            db, latitude, longitude, settings.DUPLICATE_RADIUS_M
        )
        if hits:
            complaint, dist = hits[0]
            return {"complaint": complaint, "reason": "same_location", "distance_m": round(dist, 1)}

    if image_hash:
        best = None
        for c in complaint_repository.list_unresolved_with_hash(db):
            if has_gps and c.latitude is not None and c.longitude is not None:
                if haversine_m(latitude, longitude, c.latitude, c.longitude) > IMAGE_MATCH_MAX_GPS_M:
                    continue
            dist = hamming(c.image_hash, image_hash)
            if dist <= settings.DUPLICATE_HASH_DISTANCE and (best is None or dist < best[1]):
                best = (c, dist)
        if best:
            return {"complaint": best[0], "reason": "similar_image", "hash_distance": best[1]}

    return None
