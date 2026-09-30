"""
app/schemas/detection.py
--------------------------
Pydantic response models (DTOs) for the prediction feature.
"""
from typing import List, Optional

from pydantic import BaseModel


class Detection(BaseModel):
    class_: str
    confidence: float
    box: List[int]
    severity: str

    class Config:
        fields = {"class_": "class"}
        populate_by_name = True


class PredictResponse(BaseModel):
    detections: List[dict]
    num_potholes: int
    overall_severity: str
    max_confidence: float
    complaint: Optional[dict] = None


class BatchPredictItem(PredictResponse):
    filename: Optional[str] = None
    error: Optional[str] = None


class BatchPredictResponse(BaseModel):
    count: int
    results: List[dict]
