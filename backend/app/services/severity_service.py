"""
app/services/severity_service.py
------------------------------------
Maps a detection (confidence + relative bounding-box size) to a
human-readable severity level. In this single-class model ("pothole"),
severity is derived from a combination of detection confidence and how
much of the frame the pothole occupies (a rough proxy for real-world
size when camera distance is roughly constant, e.g. a phone held at
chest height over the road).

This module is intentionally simple/interpretable so it is easy to
swap in a size-calibrated version (e.g. using camera intrinsics or a
multi-class model with Low/Medium/High/Critical as separate YOLO
classes) later without touching the rest of the backend.
"""
from typing import Dict, List

from app.core.constants import SEVERITY_ORDER


def classify_severity(confidence: float, box_area_ratio: float) -> str:
    """
    confidence: model confidence score for the detection (0-1)
    box_area_ratio: bounding box area / total image area (0-1)
    """
    score = 0.5 * confidence + 0.5 * min(box_area_ratio * 6, 1.0)

    if score < 0.35:
        return "Low"
    elif score < 0.55:
        return "Medium"
    elif score < 0.75:
        return "High"
    else:
        return "Critical"


def summarize_detections(detections: List[Dict]) -> Dict:
    """
    detections: list of {"confidence": float, "severity": str, ...}
    Returns overall complaint-level severity = worst-case among all detections.
    """
    if not detections:
        return {
            "overall_severity": "None", "max_confidence": 0.0,
            "avg_confidence": 0.0, "min_confidence": 0.0,
        }

    worst = max(detections, key=lambda d: SEVERITY_ORDER[d["severity"]])
    confs = [d["confidence"] for d in detections]
    return {
        "overall_severity": worst["severity"],
        "max_confidence": max(confs),
        "avg_confidence": sum(confs) / len(confs),
        "min_confidence": min(confs),
    }
