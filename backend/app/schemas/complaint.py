"""
app/schemas/complaint.py
--------------------------
Pydantic response models (DTOs) for the complaints feature. Not wired as
`response_model=` (the services already return plain dicts shaped like
this), kept for readers/docs and for anyone who wants to add typed
responses later.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ComplaintOut(BaseModel):
    id: int
    complaint_id: str
    image_path: str
    annotated_image_path: Optional[str] = None
    num_potholes: int
    confidence: Optional[float] = None
    avg_confidence: Optional[float] = None
    min_confidence: Optional[float] = None
    detections: List[dict] = []
    severity: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    date_reported: Optional[str] = None
    status: str
    department: Optional[str] = None
    assigned_at: Optional[str] = None
    resolved_at: Optional[str] = None
    after_image_path: Optional[str] = None
    after_annotated_path: Optional[str] = None
    after_num_potholes: Optional[int] = None
    resolution_note: Optional[str] = None
    report_count: int = 1

    class Config:
        from_attributes = True


class ComplaintListOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ComplaintOut]


class StatusUpdateIn(BaseModel):
    status: str = Field(..., description="One of: Open, Assigned, In Progress, Resolved")
    note: Optional[str] = None


class AssignIn(BaseModel):
    department: str
    note: Optional[str] = None


class DeleteOut(BaseModel):
    deleted: str
