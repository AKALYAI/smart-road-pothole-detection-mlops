"""
app/core/config.py
-------------------
Central place for environment-driven settings so the rest of the app
stays readable. Equivalent to FarmVerse's `config/` package.

Set these as real environment variables in production. Defaults here are
safe for local development / demos only.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../backend
REPO_ROOT = BASE_DIR.parent


class Settings:
    # --- App info ---------------------------------------------------
    APP_TITLE = "Smart Road Pothole Detection & Management System"
    APP_DESCRIPTION = "YOLOv8-powered pothole detection API with complaint management."
    APP_VERSION = "2.0.0"

    # --- Auth ---------------------------------------------------------
    # API key required for write-ish / prediction endpoints. Default is a
    # demo key so the project runs out of the box — CHANGE THIS before
    # deploying anywhere real, and set API_KEY as a real env var instead.
    API_KEY = os.environ.get("API_KEY", "roadwatch-demo-key")

    # Set REQUIRE_API_KEY=false to disable auth entirely (e.g. for quick
    # local testing / grading where a mentor doesn't have the key).
    REQUIRE_API_KEY = os.environ.get("REQUIRE_API_KEY", "true").lower() != "false"

    # --- User accounts (JWT) ------------------------------------------
    # Admin/citizen login. CHANGE SECRET_KEY and the admin password before
    # deploying anywhere real (set them as environment variables).
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me-please-32-bytes-min")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 480))
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    AUTH_RATE_LIMIT = os.environ.get("AUTH_RATE_LIMIT", "10/minute")

    # --- Duplicate detection ------------------------------------------------
    # A new report is treated as a duplicate of an unresolved complaint if it
    # is within DUPLICATE_RADIUS_M metres, or if the photo is near-identical
    # (256-bit dHash differs by <= DUPLICATE_HASH_DISTANCE bits).
    DUPLICATE_RADIUS_M = float(os.environ.get("DUPLICATE_RADIUS_M", 25))
    DUPLICATE_HASH_DISTANCE = int(os.environ.get("DUPLICATE_HASH_DISTANCE", 12))

    # --- High-severity alerts ---------------------------------------------------
    ALERT_SEVERITIES = ("High", "Critical")
    # Optional: POST a JSON payload here (Slack/Teams/Discord-style webhook or
    # your own service) whenever a High/Critical pothole is filed.
    ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")

    # --- Uploads --------------------------------------------------------
    UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", 10))
    MAX_BATCH_FILES = int(os.environ.get("MAX_BATCH_FILES", 10))
    ALLOWED_CONTENT_TYPES = ("image/jpeg", "image/png", "image/jpg", "image/webp")

    # --- Model / inference -----------------------------------------------
    MODEL_PATH = os.environ.get("MODEL_PATH", str(REPO_ROOT / "models" / "best.pt"))
    
    CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", 0.25))
    PREDICT_RATE_LIMIT = os.environ.get("PREDICT_RATE_LIMIT", "20/minute")

    # --- Drift monitoring -------------------------------------------------
    BASELINE_PATH = REPO_ROOT / "models" / "baseline_stats.json"
    DRIFT_MIN_DETECTIONS = 10
    DRIFT_PSI_THRESHOLD = 0.25   # common rule of thumb: >0.25 = significant shift

    # --- Email notifications ------------------------------------------------
    # Best-effort SMTP notification when a complaint's status changes. If
    # SMTP_HOST is unset, emails are just logged to the console (useful for
    # local dev/demo — no mail server required).
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() != "false"
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "roadwatch@example.com")

    # --- Zones / road health -------------------------------------------------
    # A complaint is auto-assigned to the nearest zone if it's within the
    # zone's radius. Health score weights are intentionally simple/interpretable.
    ZONE_HEALTH_WEIGHTS = {"Low": 2, "Medium": 5, "High": 10, "Critical": 18}

    # --- Dataset management ---------------------------------------------------
    DATASET_UPLOAD_DIR = Path(os.environ.get(
        "DATASET_UPLOAD_DIR", str(REPO_ROOT / "data" / "pothole_dataset" / "uploaded")
    ))

    # --- MLflow (read-only, for model version comparison) --------------------
    MLFLOW_DB_PATH = Path(
    os.environ.get(
        "MLFLOW_DB_PATH",
        str(REPO_ROOT / "mlflow_tracking" / "mlflow.db")
    )
    )
    DRIFT_WINDOW_SIZE = 50
    DRIFT_THRESHOLD_SIGMA = 1.5

    # --- Static dirs --------------------------------------------------
    FRONTEND_DIR = REPO_ROOT / "frontend"

    # --- Database -------------------------------------------------------
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'pothole_complaints.db'}")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
