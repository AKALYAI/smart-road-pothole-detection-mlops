"""
app/routers/models_router.py
--------------------------------
GET /models/versions      — compare YOLO training runs logged in MLflow   [admin]
                             (params + metrics + which one is currently serving)
GET /models/performance   — active model's Precision/Recall/F1/mAP +      [admin]
                             average inference time (Model Performance
                             Dashboard + Inference Performance features)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin
from app.db.session import get_db
from app.services import model_registry_service

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("/versions")
def list_versions(user: CurrentUser = Depends(require_admin)):
    return model_registry_service.list_runs()


@router.get("/performance")
def performance(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return model_registry_service.performance_summary(db)
