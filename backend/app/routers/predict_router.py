"""
app/routers/predict_router.py
---------------------------------
POST /predict         — run YOLOv8 on ONE uploaded image, return
                         detections + annotated image + a stored
                         complaint record (or merges into an existing one
                         if it looks like a repeat report of the same pothole)
POST /predict/batch    — same, for up to MAX_BATCH_FILES images at once
                         (e.g. a street's worth of photos)

If the caller is logged in (Authorization: Bearer <token>), the complaint
is tagged with their username as `reporter`. Anonymous reports still work.

This router only handles HTTP concerns (parsing the upload, status
codes). All actual work is delegated to the detection/complaint services.
"""
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user_optional, verify_api_key
from app.db.session import get_db
from app.services import complaint_service, detection_service
from app.utils.image_utils import draw_boxes, validate_upload

router = APIRouter(tags=["Prediction"])
limiter = Limiter(key_func=get_remote_address)


def _predict_one(pil_img: Image.Image):
    """Runs detection and draws the annotated overlay for one image."""
    detections, img_bgr, inference_ms = detection_service.run_detection_on_image(pil_img)
    annotated_bgr = draw_boxes(img_bgr.copy(), detections)
    return detections, annotated_bgr, inference_ms


def _reporter(authorization: Optional[str]) -> Optional[str]:
    user = get_current_user_optional(authorization)
    return user.username if user else None


@router.post("/predict", dependencies=[Depends(verify_api_key)])
@limiter.limit(settings.PREDICT_RATE_LIMIT)
async def predict(
    request: Request,
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    notify_email: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    if not detection_service.is_model_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded. Train the model first (scripts/train.py).")

    contents = await file.read()
    validate_upload(file, contents)
    try:
        pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

    detections, annotated_bgr, inference_ms = _predict_one(pil_img)
    result = complaint_service.save_and_file_complaint(
        pil_img, annotated_bgr, detections, latitude, longitude, address, db,
        reporter=_reporter(authorization), notify_email=notify_email, inference_ms=inference_ms,
    )
    return JSONResponse(result)


@router.post("/predict/batch", dependencies=[Depends(verify_api_key)])
@limiter.limit(settings.PREDICT_RATE_LIMIT)
async def predict_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Run detection on multiple images in one call — e.g. a municipal
    worker uploading every photo taken along one street in one go."""
    if not detection_service.is_model_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded. Train the model first (scripts/train.py).")
    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(status_code=400, detail=f"Max {settings.MAX_BATCH_FILES} files per batch request.")

    reporter = _reporter(authorization)
    results = []
    for file in files:
        contents = await file.read()
        try:
            validate_upload(file, contents)
            pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
        except HTTPException as e:
            results.append({"filename": file.filename, "error": e.detail})
            continue
        except Exception:
            results.append({"filename": file.filename, "error": "Invalid image file."})
            continue

        detections, annotated_bgr, inference_ms = _predict_one(pil_img)
        result = complaint_service.save_and_file_complaint(
            pil_img, annotated_bgr, detections, latitude, longitude, address, db,
            reporter=reporter, inference_ms=inference_ms,
        )
        result["filename"] = file.filename
        results.append(result)

    return JSONResponse({"count": len(results), "results": results})
