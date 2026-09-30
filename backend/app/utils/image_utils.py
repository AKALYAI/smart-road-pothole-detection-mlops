"""
app/utils/image_utils.py
---------------------------
Small, stateless image helpers shared by the prediction feature:
drawing severity-colored boxes on the annotated image, and validating
an uploaded file before it's handed to the model.
"""
import cv2
from fastapi import HTTPException, UploadFile

from app.core.config import settings

SEVERITY_COLORS = {
    "Low": (0, 200, 0),
    "Medium": (0, 200, 255),
    "High": (0, 100, 255),
    "Critical": (0, 0, 255),
}


def draw_boxes(image_bgr, detections):
    """Draw a colored box + severity/confidence label for each detection."""
    for det in detections:
        x1, y1, x2, y2 = det["box"]
        color = SEVERITY_COLORS.get(det["severity"], (255, 255, 255))
        cv2.rectangle(image_bgr, (x1, y1), (x2, y2), color, 3)
        label = f"{det['severity']} {det['confidence']:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(image_bgr, (x1, max(0, y1 - th - 10)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(
            image_bgr, label, (x1 + 3, max(15, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA,
        )
    return image_bgr


def validate_upload(file: UploadFile, contents: bytes) -> None:
    """Raises HTTPException if the upload fails type/size checks."""
    if file.content_type not in settings.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use JPG, PNG, or WEBP.",
        )
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f}MB). Max is {settings.MAX_UPLOAD_MB}MB.",
        )
