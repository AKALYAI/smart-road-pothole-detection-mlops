"""
app/services/model_registry_service.py
------------------------------------------
Model VERSION comparison, read straight from the MLflow tracking store
(mlflow_tracking/mlflow.db). Opened read-only with sqlite3, so the API does
not need the `mlflow` package (or a running MLflow server).

Every training run logged by scripts/train.py is a "model version": its
parameters, final metrics, and (for runs made after this update) the SHA-256
of the exported best.pt, which lets us mark which run is serving traffic.
"""
import datetime
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

METRICS = ["precision", "recall", "mAP50", "mAP50-95"]
PARAMS = ["base_model", "epochs", "imgsz", "batch"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _active_model_info() -> dict:
    p = Path(settings.MODEL_PATH)
    if not p.exists():
        return {"path": str(p), "exists": False}
    st = p.stat()
    return {
        "path": str(p), "exists": True, "size_mb": round(st.st_size / 1e6, 2),
        "modified": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "sha256": _sha256(p),
    }


def _pick(latest: Dict[str, float], name: str) -> Optional[float]:
    """Final metric under the name train.py logs it, with fallbacks for
    ultralytics' own 'metrics/mAP50(B)'-style keys (MLflow strips the brackets)."""
    for key in (name, f"metrics/{name}B", f"metrics/{name}"):
        if key in latest and latest[key] is not None:
            return latest[key]
    return None


def list_runs() -> dict:
    active = _active_model_info()
    db_path = Path(settings.MLFLOW_DB_PATH)
    if not db_path.exists():
        return {"available": False, "message": f"No MLflow store at {db_path}", "active_model": active, "runs": []}

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        runs = conn.execute(
            """SELECT r.run_uuid, r.name, r.status, r.start_time, r.end_time, e.name AS experiment
               FROM runs r JOIN experiments e ON e.experiment_id = r.experiment_id
               WHERE r.lifecycle_stage = 'active'
               ORDER BY r.start_time DESC"""
        ).fetchall()

        out: List[dict] = []
        for r in runs:
            uid = r["run_uuid"]
            latest = {m["key"]: m["value"] for m in conn.execute(
                "SELECT key, value FROM latest_metrics WHERE run_uuid = ?", (uid,))}
            params = {p["key"]: p["value"] for p in conn.execute(
                "SELECT key, value FROM params WHERE run_uuid = ? AND key IN (%s)" % ",".join("?" * len(PARAMS)),
                (uid, *PARAMS))}
            tags = {t["key"]: t["value"] for t in conn.execute(
                "SELECT key, value FROM tags WHERE run_uuid = ? AND key IN ('model_sha256', 'model_version')", (uid,))}

            start, end = r["start_time"], r["end_time"]
            out.append({
                "run_id": uid,
                "name": r["name"],
                "experiment": r["experiment"],
                "status": r["status"],
                "started": datetime.datetime.fromtimestamp(start / 1000).isoformat(timespec="seconds") if start else None,
                "duration_s": round((end - start) / 1000, 1) if start and end else None,
                "params": params,
                "metrics": {m: _pick(latest, m) for m in METRICS},
                "model_sha256": tags.get("model_sha256"),
                "is_active": bool(tags.get("model_sha256") and active.get("sha256") == tags["model_sha256"]),
            })
    finally:
        conn.close()

    # "best" = highest mAP50, ties broken by mAP50-95, among finished runs that have metrics
    finished = [r for r in out if r["status"] == "FINISHED" and r["metrics"]["mAP50"] is not None]
    best = max(finished, key=lambda r: (r["metrics"]["mAP50"], r["metrics"]["mAP50-95"] or 0), default=None)
    for r in out:
        r["is_best"] = best is not None and r["run_id"] == best["run_id"]
        r["delta_vs_best"] = (
            {m: (round(r["metrics"][m] - best["metrics"][m], 4)
                 if r["metrics"][m] is not None and best["metrics"][m] is not None else None)
             for m in METRICS}
            if best else None
        )
    return {"available": True, "active_model": active, "best_run_id": best["run_id"] if best else None, "runs": out}


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None or (precision + recall) == 0:
        return None
    return round(2 * precision * recall / (precision + recall), 4)


def performance_summary(db) -> dict:
    """Model Performance Dashboard: the metrics of whichever run is
    currently SERVING (its weights' sha256 matches models/best.pt), plus
    F1 (derived — YOLO/MLflow don't log it directly) and average
    inference time from recent /predict calls (Inference Performance)."""
    from app.services import drift_service

    registry = list_runs()
    active_run = next((r for r in registry["runs"] if r.get("is_active")), None)
    fallback = active_run is None and registry["runs"]
    run = active_run or (registry["runs"][0] if fallback else None)

    metrics = dict(run["metrics"]) if run else {"precision": None, "recall": None, "mAP50": None, "mAP50-95": None}
    metrics["f1"] = _f1(metrics.get("precision"), metrics.get("recall"))

    return {
        "available": registry["available"],
        "run_id": run["run_id"] if run else None,
        "run_name": run["name"] if run else None,
        "is_confirmed_active": bool(active_run),  # False = best-guess (no sha256 tag matched models/best.pt)
        "metrics": metrics,
        "avg_inference_ms": drift_service.avg_inference_ms(db),
        "message": None if run else "No training runs logged yet — run scripts/train.py.",
    }
