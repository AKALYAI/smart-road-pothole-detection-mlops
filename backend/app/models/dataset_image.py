"""
app/models/dataset_image.py
-------------------------------
Tracks images an admin has uploaded for future training (Dataset Management
feature). Files themselves live under settings.DATASET_UPLOAD_DIR; this
table is just the catalog (who uploaded what, when, and whether it has a
YOLO label file yet).
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.db.session import Base
from app.utils.timeutil import utcnow


class DatasetImage(Base):
    __tablename__ = "dataset_images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, unique=True)  # stored filename under DATASET_UPLOAD_DIR/images
    original_name = Column(String, nullable=True)
    has_label = Column(Boolean, default=False)               # a matching YOLO .txt was uploaded too
    label_filename = Column(String, nullable=True)
    uploaded_by = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    used_in_training = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "has_label": bool(self.has_label),
            "uploaded_by": self.uploaded_by,
            "notes": self.notes,
            "used_in_training": bool(self.used_in_training),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "url": f"/dataset-images/{self.filename}",
        }
