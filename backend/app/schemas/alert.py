"""app/schemas/alert.py — DTOs for the high-severity alerts feature."""
from typing import Optional

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    complaint_id: str
    severity: str
    message: str
    created_at: Optional[str] = None
    acknowledged: bool
    acknowledged_by: Optional[str] = None
