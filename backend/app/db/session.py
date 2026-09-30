"""
app/db/session.py
------------------
SQLAlchemy engine + session setup (SQLite by default), table creation, a
tiny "add missing columns" migration for existing SQLite files, and seeding
of the default admin account.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Columns added to EXISTING tables after their first release — applied by
# _add_missing_columns() so old SQLite databases keep working without a
# real migration tool (Alembic). {table: {column: sql_type}}
_NEW_COLUMNS = {
    "complaints": {
        "avg_confidence": "FLOAT",
        "min_confidence": "FLOAT",
        "detections_json": "TEXT",
        "department": "VARCHAR",
        "assigned_at": "DATETIME",
        "resolved_at": "DATETIME",
        "after_image_path": "VARCHAR",
        "after_annotated_path": "VARCHAR",
        "after_num_potholes": "INTEGER",
        "resolution_note": "VARCHAR",
        "image_hash": "VARCHAR",
        "report_count": "INTEGER DEFAULT 1",
        "reporter": "VARCHAR",
        # v2.1 — reports, email notify, inference timing, zones, human-in-the-loop
        "notify_email": "VARCHAR",
        "inference_ms": "FLOAT",
        "zone_id": "INTEGER",
        "verified": "VARCHAR",
        "corrected_severity": "VARCHAR",
        "corrected_num_potholes": "INTEGER",
        "correction_note": "VARCHAR",
        "corrected_by": "VARCHAR",
        "corrected_at": "DATETIME",
    },
    "users": {
        "email": "VARCHAR",
    },
    "prediction_logs": {
        "inference_ms": "FLOAT",
    },
}


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns():
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, columns in _NEW_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))


def init_db():
    """Create tables, migrate old ones, seed the admin user."""
    # importing registers the tables on Base
    from app.models import (  # noqa: F401
        alert,
        audit_log,
        complaint,
        complaint_event,
        dataset_image,
        prediction_log,
        user,
        zone,
    )

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()

    settings.DATASET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (settings.DATASET_UPLOAD_DIR / "images").mkdir(parents=True, exist_ok=True)
    (settings.DATASET_UPLOAD_DIR / "labels").mkdir(parents=True, exist_ok=True)

    from app.services import auth_service

    db = SessionLocal()
    try:
        auth_service.ensure_admin(db)
    finally:
        db.close()
