"""
app/schemas/insights.py
--------------------------
Pydantic response models (DTOs) for the dashboard/analytics feature.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel


class LocationPoint(BaseModel):
    complaint_id: str
    lat: float
    lng: float
    severity: str
    status: str
    department: Optional[str] = None
    report_count: int = 1


class TrendPoint(BaseModel):
    period: str
    total: int
    moving_avg: float


class TrendOut(BaseModel):
    period: str
    points: List[dict]
    total: int
    change_pct: Optional[float] = None
    peak: Optional[dict] = None


class HotspotOut(BaseModel):
    lat: float
    lng: float
    complaints: int
    score: float
    max_severity: str


class InsightsOut(BaseModel):
    total_complaints: int
    by_severity: Dict[str, int]
    by_status: Dict[str, int]
    by_department: Dict[str, int]
    unassigned_open: int
    urgent_open: int
    geotagged: int
    duplicates_merged: int
    avg_resolution_hours: Optional[float] = None
    trend: List[TrendPoint]
