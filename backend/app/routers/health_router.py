"""
app/routers/health_router.py
--------------------------------
GET /health — service + model health check.
"""
from fastapi import APIRouter

from app.core.config import settings
from app.services import detection_service

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": detection_service.is_model_loaded(),
        "model_path": settings.MODEL_PATH,
        "auth_required": settings.REQUIRE_API_KEY,
        "app_version": settings.APP_VERSION,
        "database_configured": bool(settings.DATABASE_URL),
        "mlflow_store_exists": settings.MLFLOW_DB_PATH.exists(),
        "dataset_dir_exists": settings.DATASET_UPLOAD_DIR.exists(),
    }
