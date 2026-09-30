# RoadWatch — Smart Road Pothole Detection & Management System

An end-to-end MLOps system that detects potholes in road images using **YOLOv8**,
tracks experiments with **MLflow**, versions data with **DVC**, serves predictions
through a **FastAPI** backend backed by **SQLite**, and presents everything in a
**HTML/CSS/JS** dashboard: photo/camera capture with GPS, a public tracking page,
a live map with a severity heatmap, a citizen/admin login split, a full ticket
workflow (assignment, status, before/after repair photos), analytics (trends,
model confidence, hotspots), model-drift monitoring, MLflow version comparison,
and Docker/CI-CD deployment.

## v2.0 — what's new

| Feature | Where |
|---|---|
| 📍 GPS complaint mapping + 🗺️ heatmap | `frontend` Map tab, `GET /insights/map` |
| 📊 Severity analytics + 📈 trend analysis (daily/weekly/monthly) | `frontend` Analytics tab, `GET /insights`, `GET /insights/trends` |
| 🔔 High-severity alerts (+ optional webhook) | `app/services/alert_service.py`, `GET/PATCH /alerts*` |
| 👤 Admin login, citizen accounts, role-gated dashboards | `app/routers/auth_router.py`, JWT via `app/core/tokens.py` |
| 🎫 Status tracking Open → Assigned → In Progress → Resolved | `app/core/constants.py`, `PATCH /complaints/{id}/status` |
| 👨‍🔧 Department assignment | `PATCH /complaints/{id}/assign` |
| 🔄 Duplicate detection (GPS radius + image dHash) | `app/services/duplicate_service.py` |
| 📸 Before/after repair photos (auto re-verified by the model) | `POST /complaints/{id}/after-image` |
| 🤖 Model confidence analysis | `GET /insights/confidence` |
| 📉 Model drift monitoring (z-score + PSI, persisted history) | `app/services/drift_service.py`, `GET /drift*` |
| 🧪 Model version comparison (MLflow) | `app/services/model_registry_service.py`, `GET /models/versions` |
| 🔁 Automatic retraining pipeline | `scripts/retrain_pipeline.py` |
| 🐳 Docker deployment (non-root, healthcheck, CPU-only torch) | `Dockerfile`, `docker-compose.yml` |
| ⚙️ CI/CD (tests, Docker build+smoke test, optional GHCR publish) | `.github/workflows/ci.yml` |

New backend env vars (see `.env.example`): `SECRET_KEY`, `ADMIN_USERNAME`,
`ADMIN_PASSWORD`, `ALERT_WEBHOOK_URL`, `DUPLICATE_RADIUS_M`,
`DUPLICATE_HASH_DISTANCE`. **Change `SECRET_KEY` and `ADMIN_PASSWORD` before any
real deployment** — the defaults are for local demos only.

Run the test suite: `cd backend && pip install -r requirements.txt pytest httpx && pytest tests -q`
(`tests/test_pure.py` needs no extra deps; `tests/test_api.py` and `tests/test_v3_features.py` need fastapi/httpx/reportlab/openpyxl).

## v2.1 — what's new

| Feature | Where |
|---|---|
| 📜 PDF/Excel report generation (same filters as the ticket search) | `app/services/report_service.py`, `GET /complaints/export.{pdf,xlsx}` |
| 🔍 Advanced search: multi-severity, zone filter, sortable columns | `GET /complaints?severity=High,Critical&sort_by=...` |
| 📊 Model Performance Dashboard (Precision/Recall/F1/mAP) | `frontend` Monitor tab, `GET /models/performance` |
| ⚡ Inference performance (per-detection + rolling average) | `app/services/detection_service.py` (timed), `GET /models/performance` |
| 📧 Email notification on status change (SMTP, or console fallback with no config) | `app/services/email_service.py` |
| 📱 PWA — installable, camera+GPS capture already built in | `frontend/manifest.json`, `frontend/service-worker.js` |
| 🗃️ Dataset management (stage images + YOLO labels for retraining) | `app/services/dataset_service.py`, `GET/POST/DELETE /dataset/images*` |
| 👨‍💻 Human-in-the-loop corrections (admin confirms/corrects a detection) | `PATCH /complaints/{id}/correct` |
| 🧾 Audit logs (who changed what, when — across the whole app) | `app/services/audit_service.py`, `GET /audit` |
| 🛣️ Road Health Score (0–100 per zone, from severity/backlog/resolution speed) | `app/services/zone_service.py`, `GET /zones*` |
| 🌐 Multi-zone management (complaints auto-assigned to the nearest zone) | `app/routers/zones_router.py`, `frontend` Road health tab |

New env vars: `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/`SMTP_USE_TLS`/`EMAIL_FROM`
(leave `SMTP_HOST` unset to just print emails to the console — no mail server
needed for local use), `DATASET_UPLOAD_DIR`. New Python deps: `reportlab`, `openpyxl`.

```
Road Image ──▶ YOLOv8 (best.pt) ──▶ Bounding Boxes + Confidence
                                            │
                                            ▼
                                  Severity Classifier (Low/Med/High/Critical)
                                            │
                                            ▼
                              SQLite Complaint Record (ticket)
                                            │
                                            ▼
                         Dashboard: Detect · Tickets · Insights
```

## ⚠️ About the dataset

This repo ships with a **synthetically generated** ~200-image road dataset
(`scripts/generate_dataset.py`) — asphalt-textured backgrounds with irregular
dark "pothole" blobs vs. clean road images — so the *entire* pipeline (train →
track → serve → dashboard) runs offline, deterministically, and reproducibly
without needing external downloads or API keys.

**To use a real-world dataset** (e.g. a Roboflow/Kaggle pothole dataset):
1. Replace the contents of `data/pothole_dataset/images/{train,val,test}` and
   `data/pothole_dataset/labels/{train,val,test}` with your own images + YOLO
   `.txt` labels (class `0 = pothole`).
2. Skip `generate_dataset.py` and go straight to training.
3. Everything downstream (training, MLflow, FastAPI, dashboard) works unchanged.

The model shipped in `models/best.pt` was trained on the synthetic set and
reaches mAP50 = 0.995 / precision = 1.0 / recall = 1.0 on its held-out test
split — strong on synthetic data, but you should retrain on real photos
before relying on it for production road inspections.

## Project structure

```
pothole-system/
├── data/pothole_dataset/       # YOLO-format dataset (DVC-tracked)
│   ├── images/{train,val,test}
│   ├── labels/{train,val,test}
│   └── data.yaml
├── scripts/
│   ├── generate_dataset.py     # synthetic dataset generator
│   ├── train.py                # YOLOv8 training + MLflow logging
│   └── evaluate.py             # test-split + external-image evaluation
├── models/
│   └── best.pt                 # trained YOLOv8 weights (final deliverable)
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app factory — wires up routers only
│   │   ├── core/
│   │   │   ├── config.py       # all env-driven settings in one place
│   │   │   └── security.py     # X-API-Key auth dependency
│   │   ├── db/
│   │   │   └── session.py      # SQLAlchemy engine/session/init_db
│   │   ├── models/              # ORM entities (one file per table)
│   │   │   └── complaint.py
│   │   ├── schemas/             # Pydantic request/response DTOs
│   │   │   ├── complaint.py
│   │   │   ├── detection.py
│   │   │   ├── insights.py
│   │   │   └── drift.py
│   │   ├── repository/          # raw DB queries only — no business logic
│   │   │   └── complaint_repository.py
│   │   ├── services/             # business logic, one file per feature
│   │   │   ├── detection_service.py   # YOLO model load + inference
│   │   │   ├── severity_service.py    # severity classification
│   │   │   ├── complaint_service.py   # save/list/update/delete/export
│   │   │   ├── insights_service.py    # dashboard aggregation
│   │   │   └── drift_service.py       # drift monitoring
│   │   ├── routers/              # HTTP endpoints, one file per feature
│   │   │   ├── health_router.py       # GET /health
│   │   │   ├── predict_router.py      # POST /predict, /predict/batch
│   │   │   ├── complaints_router.py   # /complaints CRUD + CSV export
│   │   │   ├── insights_router.py     # GET /insights
│   │   │   └── drift_router.py        # GET /drift
│   │   └── utils/
│   │       └── image_utils.py   # box-drawing + upload validation helpers
│   ├── requirements.txt
│   └── uploads/                 # stored original + annotated images
├── frontend/
│   ├── index.html              # dashboard shell (Detect / Tickets / Insights)
│   ├── style.css               # civic road-infrastructure design system
│   └── script.js                # upload, camera, GPS, charts, map logic
├── mlflow_tracking/mlflow.db   # MLflow experiment store (sqlite)
├── dvc.yaml                    # DVC pipeline: generate → train → evaluate
├── .dvc/, data/pothole_dataset.dvc   # DVC tracking metadata
└── requirements.txt
```

## 1. Setup

```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

> `torch` installs automatically as an `ultralytics` dependency. If you have a
> GPU, install the matching CUDA build from https://pytorch.org/get-started/locally/
> **before** installing `ultralytics` for faster training.

## 2. Dataset (already generated + DVC-tracked)

The dataset is already generated and committed under DVC. To regenerate it,
or pull it in a fresh clone:

```bash
# regenerate from scratch
python scripts/generate_dataset.py --count 200 --out data/pothole_dataset

# OR, in a fresh clone with the DVC remote configured, pull the tracked version
dvc pull
```

To version a new dataset revision:

```bash
dvc add data/pothole_dataset
git add data/pothole_dataset.dvc
git commit -m "Update dataset"
dvc push   # if a remote is configured
```

## 3. Train the model

```bash
python scripts/train.py --epochs 30 --imgsz 640 --batch 8
```

This will:
- Fine-tune `yolov8n.pt` on `data/pothole_dataset`
- Log parameters, per-epoch metrics (loss, precision, recall, mAP50, mAP50-95),
  and the final model as an **MLflow** run (`mlflow_tracking/mlflow.db`)
- Copy the best checkpoint to `models/best.pt`

View the MLflow UI:

```bash
mlflow ui --backend-store-uri sqlite:///mlflow_tracking/mlflow.db
# open http://localhost:5000
```

## 4. Evaluate on unseen images

```bash
# held-out test split (never seen during training)
python scripts/evaluate.py --split test

# + sanity-check against a folder of real-world / external photos
python scripts/evaluate.py --split test --external_dir /path/to/real_photos
```

## 5. Run the backend

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Key endpoints:

| Method | Path                          | Description                                   |
|--------|-------------------------------|------------------------------------------------|
| GET    | `/health`                     | Model + service health check                  |
| POST   | `/predict`                    | Upload image (+ optional GPS) → detections, annotated image, auto-filed complaint |
| GET    | `/complaints`                 | List all complaint tickets                     |
| GET    | `/complaints/{id}`            | Get one ticket                                 |
| PATCH  | `/complaints/{id}/status`     | Update ticket status (Open/In Progress/Resolved) |
| GET    | `/insights`                   | Aggregate stats for charts + map               |

Interactive API docs: `http://localhost:8000/docs`

## 6. Run the frontend

The FastAPI app already serves the dashboard at `http://localhost:8000/app`
(static mount). Alternatively, open `frontend/index.html` directly in a
browser, or serve it separately:

```bash
cd frontend
python -m http.server 5500
# open http://localhost:5500
```

The dashboard auto-detects `localhost`/`127.0.0.1` and points at
`http://localhost:8000` for the API — edit `API_BASE` in `script.js` if you
deploy the backend elsewhere.

### Dashboard features
- **Detect** — drag-and-drop or camera-capture a road photo, optionally
  attach your current GPS location, and run detection. Annotated result with
  bounding boxes + severity is shown immediately and a complaint is filed
  automatically when potholes are found.
- **Tickets** — table of every filed complaint (thumbnail, ID, severity,
  confidence, location, date, status) with an inline status dropdown.
- **Insights** — total/open/critical/resolved stat cards, a severity donut
  chart, a complaints-per-day trend chart, and a Leaflet map of geotagged
  complaints colored by severity.

## 7. Severity levels

Severity is derived from detection confidence and the pothole's relative
size in the frame:

| Severity | Meaning                                   |
|----------|--------------------------------------------|
| Low      | Small / low-confidence detection            |
| Medium   | Moderate size and/or confidence             |
| High     | Large and/or high-confidence detection      |
| Critical | Large, high-confidence — road hazard        |

See `backend/app/services/severity_service.py` to swap in a calibrated version (e.g. using known
camera height/angle, or a multi-class YOLO model with severity as separate
classes).

## 8. Reproducibility (Git + DVC + MLflow)

- **Git** tracks code (`scripts/`, `backend/`, `frontend/`).
- **DVC** tracks the dataset (`data/pothole_dataset.dvc`) so exact training
  data can be restored with `dvc pull`/`dvc checkout`, independent of git's
  binary-diffing limits.
- **MLflow** tracks every training run's parameters, per-epoch metrics, and
  model artifact so any past `best.pt` can be traced back to the exact config
  and data version that produced it.
- `dvc.yaml` defines the full pipeline (`generate_dataset → train → evaluate`)
  so `dvc repro` reruns only the stages whose dependencies changed.

```bash
dvc repro        # re-run any out-of-date pipeline stages
dvc dag           # visualize the pipeline
```

## 9. Deployment notes

- **Backend**: containerize `backend/` (add a `Dockerfile` with
  `pip install -r requirements.txt` + `uvicorn app.main:app --host 0.0.0.0`),
  deploy to any container host (Cloud Run, ECS, Render, etc.), and mount a
  persistent volume for `pothole_complaints.db` and `uploads/`.
- **Model**: bake `models/best.pt` into the image, or fetch it from an
  MLflow Model Registry / object storage (S3/GCS) at container startup via
  the `MODEL_PATH` env var.
- **Frontend**: the dashboard is static — deploy `frontend/` to any static
  host (Netlify, S3+CloudFront, GitHub Pages) and point `API_BASE` in
  `script.js` at your deployed backend URL. Or keep it served from FastAPI's
  `/app` static mount for a single-service deployment.
- **CORS**: `backend/app/main.py` currently allows all origins for development —
  restrict `allow_origins` before going to production.
- **Database**: SQLite is fine for a pilot; swap `DATABASE_URL` in
  `backend/app/db/session.py` for Postgres/MySQL when moving to production scale.

## 10. Retraining on real data

1. Collect real pothole + normal-road photos (phone camera, dashcam, CCTV).
2. Label them in YOLO format (e.g. with [Roboflow](https://roboflow.com) or
   [LabelImg](https://github.com/heartexlab/labelImg)) — class `0 = pothole`.
3. Drop images/labels into `data/pothole_dataset/{images,labels}/{train,val,test}`.
4. `dvc add data/pothole_dataset && git commit` to version the new dataset.
5. `python scripts/train.py --epochs 50 --imgsz 640` (increase epochs/imgsz
   for real photos; the defaults here are tuned for the small synthetic set).
6. `python scripts/evaluate.py --split test --external_dir <held-out photos>`
   to confirm real-world performance before promoting the new `best.pt`.


## Demo Map / Heatmap data

The Map & Heatmap view only displays complaints that contain latitude and longitude.
For local demo testing, after the backend has initialized its database, run:

```powershell
python scripts/seed_demo_geodata.py
```

This updates missing coordinates on existing complaints only. The coordinates are explicitly demo values; replace them with real GPS coordinates for deployment.

Model Monitor may show **Insufficient data** until at least 10 recent detections are available. This is an expected state, not a model failure.
