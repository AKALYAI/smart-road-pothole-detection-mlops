"""app/repository/prediction_log_repository.py"""
import datetime
import json
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.prediction_log import PredictionLog


def add(db: Session, confidences: List[float], inference_ms: Optional[float] = None) -> PredictionLog:
    row = PredictionLog(
        num_detections=len(confidences),
        max_confidence=max(confidences) if confidences else None,
        mean_confidence=(sum(confidences) / len(confidences)) if confidences else None,
        confidences_json=json.dumps([round(c, 4) for c in confidences]),
        inference_ms=inference_ms,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def recent(db: Session, n: int) -> List[PredictionLog]:
    return db.query(PredictionLog).order_by(PredictionLog.id.desc()).limit(n).all()


def since(db: Session, dt: datetime.datetime) -> List[PredictionLog]:
    return (
        db.query(PredictionLog)
        .filter(PredictionLog.created_at >= dt)
        .order_by(PredictionLog.created_at.asc())
        .all()
    )
