"""
app/models/complaint.py
------------------------
The `Complaint` ORM entity — one row per filed pothole complaint
(created automatically whenever a /predict call finds at least one NEW
pothole; repeat reports of the same pothole are merged into the original,
see services/duplicate_service.py).
"""
import json
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db.session import Base
from app.utils.timeutil import utcnow


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(
        String, unique=True, index=True, default=lambda: str(uuid.uuid4())[:8].upper()
    )
    image_path = Column(String, nullable=False)
    annotated_image_path = Column(String, nullable=True)
    num_potholes = Column(Integer, default=0)
    confidence = Column(Float, nullable=True)       # max confidence among detections
    avg_confidence = Column(Float, nullable=True)   # mean confidence among detections
    min_confidence = Column(Float, nullable=True)   # weakest detection (review candidates)
    detections_json = Column(Text, nullable=True)   # [{confidence, severity, box, ...}]
    severity = Column(String, nullable=True)        # Low / Medium / High / Critical
    latitude = Column(Float, nullable=True, index=True)
    longitude = Column(Float, nullable=True, index=True)
    address = Column(String, nullable=True)
    date_reported = Column(DateTime, default=utcnow, index=True)
    status = Column(String, default="Open", index=True)  # Open/Assigned/In Progress/Resolved

    # --- department assignment ---
    department = Column(String, nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)

    # --- resolution / before-after ---
    resolved_at = Column(DateTime, nullable=True)
    after_image_path = Column(String, nullable=True)
    after_annotated_path = Column(String, nullable=True)
    after_num_potholes = Column(Integer, nullable=True)  # model re-check of the repair photo
    resolution_note = Column(String, nullable=True)

    # --- duplicate detection ---
    image_hash = Column(String, nullable=True)      # 64-bit dHash (hex) of the original photo
    report_count = Column(Integer, default=1)       # 1 = only the original report

    reporter = Column(String, nullable=True)        # username of the citizen who reported
    notify_email = Column(String, nullable=True)    # optional — emailed on status changes

    # --- performance / zone / human-in-the-loop ---
    inference_ms = Column(Float, nullable=True)     # model inference time for this detection
    zone_id = Column(Integer, nullable=True, index=True)  # nearest Zone, if any (see models/zone.py)
    verified = Column(String, nullable=True)         # None | "correct" | "corrected" (admin review)
    corrected_severity = Column(String, nullable=True)
    corrected_num_potholes = Column(Integer, nullable=True)
    correction_note = Column(String, nullable=True)
    corrected_by = Column(String, nullable=True)
    corrected_at = Column(DateTime, nullable=True)

    def detections(self):
        try:
            return json.loads(self.detections_json) if self.detections_json else []
        except ValueError:
            return []

    def to_dict(self, public: bool = False):
        d = {
            "id": self.id,
            "complaint_id": self.complaint_id,
            "image_path": self.image_path,
            "annotated_image_path": self.annotated_image_path,
            "num_potholes": self.num_potholes,
            "confidence": self.confidence,
            "avg_confidence": self.avg_confidence,
            "min_confidence": self.min_confidence,
            "detections": self.detections(),
            "severity": self.severity,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "date_reported": self.date_reported.isoformat() if self.date_reported else None,
            "status": self.status,
            "department": self.department,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "after_image_path": self.after_image_path,
            "after_annotated_path": self.after_annotated_path,
            "after_num_potholes": self.after_num_potholes,
            "resolution_note": self.resolution_note,
            "report_count": self.report_count or 1,
            "inference_ms": self.inference_ms,
            "zone_id": self.zone_id,
            "verified": self.verified,
            "corrected_severity": self.corrected_severity,
            "corrected_num_potholes": self.corrected_num_potholes,
            "correction_note": self.correction_note,
            "corrected_by": self.corrected_by,
            "corrected_at": self.corrected_at.isoformat() if self.corrected_at else None,
        }
        if not public:
            d["reporter"] = self.reporter
        return d
