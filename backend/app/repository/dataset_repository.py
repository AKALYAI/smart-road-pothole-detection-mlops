"""app/repository/dataset_repository.py"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.dataset_image import DatasetImage


def create(db: Session, img: DatasetImage) -> DatasetImage:
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


def list_all(db: Session, limit: int = 200, offset: int = 0) -> List[DatasetImage]:
    return (
        db.query(DatasetImage)
        .order_by(DatasetImage.created_at.desc())
        .offset(offset).limit(limit).all()
    )


def count(db: Session) -> int:
    return db.query(DatasetImage).count()


def get(db: Session, image_id: int) -> Optional[DatasetImage]:
    return db.query(DatasetImage).filter(DatasetImage.id == image_id).first()


def delete(db: Session, img: DatasetImage) -> None:
    db.delete(img)
    db.commit()
