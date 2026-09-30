"""
app/schemas/drift.py
-----------------------
Pydantic response model (DTO) for the drift-monitoring feature.
"""
from typing import List, Optional

from pydantic import BaseModel


class DriftOut(BaseModel):
    status: str
    message: str
    live_mean_confidence: Optional[float] = None
    live_std_confidence: Optional[float] = None
    baseline_mean_confidence: Optional[float] = None
    baseline_std_confidence: Optional[float] = None
    z_score: Optional[float] = None
    psi: Optional[float] = None
    detection_rate: Optional[float] = None
    n_recent_samples: Optional[int] = None
    reasons: Optional[List[str]] = None
