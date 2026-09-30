"""
app/models/prediction_log.py
-----------------------------
One row per /predict inference (including images with ZERO potholes). This
is what drift monitoring reads, so it survives restarts (the old version
kept the rolling window only in memory).
"""
from sqlalchemy import Column, DateTime, Float, Integer, Text

from app.db.session import Base
from app.utils.timeutil import utcnow


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    num_detections = Column(Integer, default=0)
    max_confidence = Column(Float, nullable=True)
    mean_confidence = Column(Float, nullable=True)
    confidences_json = Column(Text, nullable=True)  # JSON list of floats
    inference_ms = Column(Float, nullable=True)      # model forward-pass time for this image
