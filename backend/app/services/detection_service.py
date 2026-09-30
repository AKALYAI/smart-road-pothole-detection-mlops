"""
app/services/detection_service.py
-------------------------------------
Owns the YOLOv8 model: loading it once at startup and running
inference on a single image. Nothing here knows about HTTP, the
database, or complaints — it only turns an image into detections.
"""
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

from app.core.config import settings
from app.services.analytics import confidence_band
from app.services.severity_service import classify_severity

_model: Optional[YOLO] = None


def load_model() -> Optional[YOLO]:
    """Loads the YOLO model from MODEL_PATH once (called on app startup)."""
    global _model
    if Path(settings.MODEL_PATH).exists():
        _model = YOLO(settings.MODEL_PATH)
        print(f"Loaded model from {settings.MODEL_PATH}")
    else:
        print(f"WARNING: model not found at {settings.MODEL_PATH}. Run scripts/train.py first.")
    return _model


def is_model_loaded() -> bool:
    return _model is not None


def get_model() -> Optional[YOLO]:
    return _model


def run_detection_on_image(pil_img: Image.Image) -> Tuple[List[dict], np.ndarray, float]:
    """Runs YOLO on one PIL image. Returns (detections, source_bgr_image, inference_ms).

    Note: this returns the *un-annotated* BGR array; drawing boxes is a
    presentation concern handled by app.utils.image_utils.draw_boxes.
    inference_ms times ONLY the model forward pass (Inference Performance
    feature) — not image decoding/resizing/drawing, so it's comparable
    across requests regardless of image size on disk.
    """
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    img_np = np.array(pil_img)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    h, w = img_bgr.shape[:2]

    t0 = time.perf_counter()
    results = _model.predict(source=img_np, conf=settings.CONF_THRESHOLD, verbose=False)
    inference_ms = (time.perf_counter() - t0) * 1000
    r = results[0]

    detections = []
    for box in r.boxes:
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        conf = float(box.conf[0])
        cls_id = int(box.cls[0])
        cls_name = _model.names.get(cls_id, "pothole")
        area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h)
        sev = classify_severity(conf, area_ratio)
        detections.append(
            {
                "class": cls_name,
                "confidence": round(conf, 4),
                "confidence_band": confidence_band(conf),  # High / Medium / Low detection quality
                "box": [x1, y1, x2, y2],
                "severity": sev,
            }
        )

    return detections, img_bgr, round(inference_ms, 2)
