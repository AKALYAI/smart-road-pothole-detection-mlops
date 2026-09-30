"""
app/main.py
-------------
FastAPI application factory for the Smart Road Pothole Detection &
Management System.

This file is intentionally thin: it creates the app, wires up
middleware/static files, includes one router per feature, and runs
startup tasks. All actual logic lives in app/services + app/routers.

Endpoints (see each router's docstring for details):
  Health        -> app/routers/health_router.py
  Auth          -> app/routers/auth_router.py       (citizen/admin login)
  Prediction    -> app/routers/predict_router.py
  Complaints    -> app/routers/complaints_router.py
  Meta          -> app/routers/meta_router.py         (departments, status lookup)
  Insights      -> app/routers/insights_router.py   (stats/map/trends/confidence/hotspots)
  Drift         -> app/routers/drift_router.py
  Models        -> app/routers/models_router.py     (MLflow version comparison + performance dashboard)
  Alerts        -> app/routers/alerts_router.py      (High/Critical alerts)
  Zones         -> app/routers/zones_router.py        (multi-zone management + road health score)
  Audit         -> app/routers/audit_router.py         (cross-cutting audit trail)
  Dataset       -> app/routers/dataset_router.py       (dataset management for retraining)

Auth: endpoints that create/modify predictions require an `X-API-Key`
header (see app/core/config.py). Set REQUIRE_API_KEY=false to disable for
local demos. Admin-only endpoints additionally require a JWT bearer token
from POST /auth/login (see app/core/security.py).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.db.session import init_db
from app.routers import (
    alerts_router,
    audit_router,
    auth_router,
    complaints_router,
    dataset_router,
    drift_router,
    health_router,
    insights_router,
    meta_router,
    models_router,
    predict_router,
    zones_router,
)
from app.routers.predict_router import limiter
from app.services import detection_service


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
    )

    # --- Rate limiting -------------------------------------------------
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # --- CORS -----------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Static files --------------------------------------------------
    app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")
    settings.DATASET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (settings.DATASET_UPLOAD_DIR / "images").mkdir(parents=True, exist_ok=True)
    app.mount(
        "/dataset-images", StaticFiles(directory=str(settings.DATASET_UPLOAD_DIR / "images")),
        name="dataset-images",
    )
    if settings.FRONTEND_DIR.exists():
        app.mount("/app", StaticFiles(directory=str(settings.FRONTEND_DIR), html=True), name="frontend")

    # --- Routers (one per feature) --------------------------------------
    app.include_router(health_router.router)
    app.include_router(meta_router.router)
    app.include_router(auth_router.router)
    app.include_router(predict_router.router)
    app.include_router(complaints_router.router)
    app.include_router(insights_router.router)
    app.include_router(drift_router.router)
    app.include_router(models_router.router)
    app.include_router(alerts_router.router)
    app.include_router(zones_router.router)
    app.include_router(audit_router.router)
    app.include_router(dataset_router.router)

    # --- Startup ----------------------------------------------------------
    @app.on_event("startup")
    def startup_event():
        init_db()
        detection_service.load_model()
        if settings.REQUIRE_API_KEY:
            print("API key auth is ON. Send header: X-API-Key: <your key>")
        else:
            print("API key auth is OFF (REQUIRE_API_KEY=false).")
        if settings.ADMIN_PASSWORD == "admin123":
            print(f"Admin login: {settings.ADMIN_USERNAME} / {settings.ADMIN_PASSWORD} "
                  f"(CHANGE via ADMIN_PASSWORD env var before deploying).")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
