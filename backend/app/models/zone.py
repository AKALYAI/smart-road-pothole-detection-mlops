"""
app/models/zone.py
---------------------
A municipal/road zone (e.g. "Ward 12" or "NH-48 Stretch A"), defined as a
center point + radius. Complaints are auto-assigned to the nearest zone
they fall within (see services/zone_service.py), which powers the
Road Health Score and multi-zone management features.
"""
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.db.session import Base
from app.utils.timeutil import utcnow


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False, default=2.0)
    description = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_km": self.radius_km,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
