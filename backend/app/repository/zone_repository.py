"""app/repository/zone_repository.py"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.zone import Zone


def create(db: Session, zone: Zone) -> Zone:
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


def list_all(db: Session) -> List[Zone]:
    return db.query(Zone).order_by(Zone.name.asc()).all()


def get(db: Session, zone_id: int) -> Optional[Zone]:
    return db.query(Zone).filter(Zone.id == zone_id).first()


def get_by_name(db: Session, name: str) -> Optional[Zone]:
    return db.query(Zone).filter(Zone.name == name).first()


def delete(db: Session, zone: Zone) -> None:
    db.delete(zone)
    db.commit()
