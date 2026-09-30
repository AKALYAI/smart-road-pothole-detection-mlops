"""
app/services/dataset_service.py
-----------------------------------
Dataset Management: lets an admin upload new road images (optionally with
a matching YOLO-format label .txt) for future training runs, without
touching a server's filesystem by hand.

Files land under settings.DATASET_UPLOAD_DIR/{images,labels}. This is a
STAGING area, deliberately separate from data/pothole_dataset/{train,val,test}
— nothing here is used for training until someone reviews it and merges it
into a real split (keeps a bad upload from silently corrupting the dataset
DVC already tracks). scripts/retrain_pipeline.py --skip-generate can point
at a merged folder once you're ready.
"""
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dataset_image import DatasetImage
from app.repository import dataset_repository

IMAGES_DIR = settings.DATASET_UPLOAD_DIR / "images"
LABELS_DIR = settings.DATASET_UPLOAD_DIR / "labels"


def save_image(
    db: Session, pil_img: Image.Image, original_name: str, uploaded_by: str,
    label_text: Optional[str] = None, notes: Optional[str] = None,
) -> DatasetImage:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    stem = uuid.uuid4().hex[:12]
    filename = f"{stem}.jpg"
    pil_img.convert("RGB").save(IMAGES_DIR / filename, quality=92)

    label_filename = None
    if label_text is not None and label_text.strip():
        label_filename = f"{stem}.txt"
        (LABELS_DIR / label_filename).write_text(label_text.strip() + "\n")

    row = DatasetImage(
        filename=filename, original_name=original_name, has_label=label_filename is not None,
        label_filename=label_filename, uploaded_by=uploaded_by, notes=notes,
    )
    return dataset_repository.create(db, row)


def list_images(db: Session, limit: int = 200, offset: int = 0) -> dict:
    total = dataset_repository.count(db)
    items = dataset_repository.list_all(db, limit=limit, offset=offset)
    labeled = sum(1 for i in items if i.has_label)
    return {"total": total, "labeled_on_page": labeled, "limit": limit, "offset": offset,
            "items": [i.to_dict() for i in items]}


def get_or_404(db: Session, image_id: int) -> DatasetImage:
    img = dataset_repository.get(db, image_id)
    if not img:
        raise HTTPException(404, "Dataset image not found")
    return img


def delete_image(db: Session, img: DatasetImage) -> None:
    (IMAGES_DIR / img.filename).unlink(missing_ok=True)
    if img.label_filename:
        (LABELS_DIR / img.label_filename).unlink(missing_ok=True)
    dataset_repository.delete(db, img)
