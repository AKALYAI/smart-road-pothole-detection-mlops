# RoadWatch — FastAPI + YOLOv8 pothole detection API + dashboard
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first (much smaller image than the default CUDA build)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY models ./models
COPY mlflow_tracking ./mlflow_tracking

# non-root user; /data holds the SQLite DB + uploads (mounted as a volume)
RUN useradd -m roadwatch && mkdir -p /data/uploads && chown -R roadwatch /data /app
USER roadwatch

WORKDIR /app/backend

ENV MODEL_PATH=/app/models/best.pt \
    DATABASE_URL=sqlite:////data/pothole_complaints.db \
    UPLOAD_DIR=/data/uploads \
    REQUIRE_API_KEY=true \
    CONF_THRESHOLD=0.25

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD curl -fs http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
