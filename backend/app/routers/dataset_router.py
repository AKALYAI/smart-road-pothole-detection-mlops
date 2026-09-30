"""
app/routers/dataset_router.py
---------------------------------
Dataset Management (admin): upload new road images — optionally with a
YOLO-format label .txt — for a future training run, list what's been
uploaded, and remove bad uploads.

GET    /dataset/images           — list uploaded images (paginated)
POST   /dataset/images           — upload one image (+ optional label)
DELETE /dataset/images/{id}      — remove an uploaded image
GET    /dataset-images/{filename} — serve the raw file (mounted separately, see main.py)
"""
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin
from app.db.session import get_db
from app.services import audit_service, dataset_service

router = APIRouter(prefix="/dataset", tags=["Dataset"])


@router.get("/images")
def list_images(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    return dataset_service.list_images(db, limit=limit, offset=offset)


@router.post("/images")
async def upload_image(
    file: UploadFile = File(...),
    label: Optional[UploadFile] = File(None, description="Optional YOLO-format .txt label file"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    contents = await file.read()
    try:
        pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Uploaded file is not a valid image.")

    label_text = None
    if label is not None:
        label_bytes = await label.read()
        try:
            label_text = label_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "Label file must be a plain-text YOLO .txt file.")

    img = dataset_service.save_image(
        db, pil_img, original_name=file.filename, uploaded_by=user.username,
        label_text=label_text, notes=notes,
    )
    audit_service.log(db, user.username, "dataset_image_uploaded", "dataset_image", str(img.id),
                       f"{file.filename}" + (" (labeled)" if img.has_label else " (unlabeled)"))
    return img.to_dict()


@router.delete("/images/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    img = dataset_service.get_or_404(db, image_id)
    filename = img.filename
    dataset_service.delete_image(db, img)
    audit_service.log(db, user.username, "dataset_image_deleted", "dataset_image", str(image_id), filename)
    return {"deleted": image_id}
