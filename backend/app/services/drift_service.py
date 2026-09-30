"""
app/services/drift_service.py
---------------------------------
Model drift monitoring. Every /predict call is persisted as a PredictionLog
row (also when NO pothole is found), so monitoring survives restarts.

Signals compared against the training-time baseline (models/baseline_stats.json,
written by scripts/compute_baseline.py):

  * mean-confidence z-score  — live mean vs baseline mean, in baseline std units
                               (flags drift when confidences fall meaningfully)
  * PSI on the confidence histogram — only if the baseline has a histogram
  * detection rate / avg detections per image — reported for context, and
    compared to the baseline detection rate when the baseline has one.

Still intentionally lightweight and interpretable — a stand-in for
Evidently/WhyLabs — but now with history so the dashboard can chart it.
"""
import datetime
import json
import statistics
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repository import prediction_log_repository
from app.services import analytics
from app.utils.timeutil import utcnow

HIST_BINS = 10


def load_baseline() -> Optional[dict]:
    if settings.BASELINE_PATH.exists():
        with open(settings.BASELINE_PATH) as f:
            return json.load(f)
    return None


def save_baseline(mean_conf: float, std_conf: float, n: int, histogram: Optional[List[float]] = None,
                  detection_rate: Optional[float] = None):
    settings.BASELINE_PATH.parent.mkdir(exist_ok=True)
    data = {"mean_confidence": mean_conf, "std_confidence": std_conf, "n_detections": n}
    if histogram is not None:
        data["histogram"] = histogram  # proportions per 0.1 confidence bin
    if detection_rate is not None:
        data["detection_rate"] = detection_rate
    with open(settings.BASELINE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def record_prediction(db: Session, confidences: List[float], inference_ms: Optional[float] = None) -> None:
    """Call after every /predict with the list of detection confidences."""
    prediction_log_repository.add(db, confidences, inference_ms=inference_ms)


def _flatten(logs) -> List[float]:
    vals: List[float] = []
    for row in logs:
        try:
            vals.extend(json.loads(row.confidences_json or "[]"))
        except ValueError:
            pass
    return vals


def check_drift(db: Session, threshold_sigma: Optional[float] = None) -> dict:
    """Are recent live predictions meaningfully different from the baseline?"""
    threshold_sigma = threshold_sigma or settings.DRIFT_THRESHOLD_SIGMA
    baseline = load_baseline()
    logs = prediction_log_repository.recent(db, settings.DRIFT_WINDOW_SIZE)
    confs = _flatten(logs)

    if baseline is None or len(confs) < settings.DRIFT_MIN_DETECTIONS:
        return {
            "status": "insufficient_data",
            "message": (
                f"Not enough data yet to assess drift (need a baseline + "
                f"{settings.DRIFT_MIN_DETECTIONS}+ recent detections; have {len(confs)})."
            ),
            "n_recent_samples": len(confs),
            "n_recent_images": len(logs),
        }

    live_mean = statistics.mean(confs)
    live_std = statistics.pstdev(confs) if len(confs) > 1 else 0.0
    baseline_mean = baseline["mean_confidence"]
    baseline_std = max(baseline["std_confidence"], 1e-6)
    z_score = (live_mean - baseline_mean) / baseline_std

    reasons = []
    if z_score < -threshold_sigma:
        reasons.append(f"mean confidence is {abs(z_score):.1f} baseline std-devs below training")

    psi_value = None
    if baseline.get("histogram") and len(baseline["histogram"]) == HIST_BINS:
        live_props = analytics.proportions(analytics.histogram(confs, HIST_BINS))
        psi_value = analytics.psi(baseline["histogram"], live_props)
        if psi_value > settings.DRIFT_PSI_THRESHOLD:
            reasons.append(f"confidence distribution shifted (PSI {psi_value} > {settings.DRIFT_PSI_THRESHOLD})")

    images_with_detection = sum(1 for r in logs if r.num_detections > 0)
    detection_rate = images_with_detection / len(logs) if logs else 0.0
    if baseline.get("detection_rate") is not None and abs(detection_rate - baseline["detection_rate"]) > 0.3:
        reasons.append(
            f"detection rate {detection_rate:.0%} vs baseline {baseline['detection_rate']:.0%}"
        )

    drifted = bool(reasons)
    return {
        "status": "drift_detected" if drifted else "stable",
        "live_mean_confidence": round(live_mean, 4),
        "live_std_confidence": round(live_std, 4),
        "baseline_mean_confidence": round(baseline_mean, 4),
        "baseline_std_confidence": round(baseline_std, 4),
        "z_score": round(z_score, 3),
        "psi": psi_value,
        "detection_rate": round(detection_rate, 3),
        "avg_detections_per_image": round(sum(r.num_detections for r in logs) / len(logs), 2) if logs else 0,
        "n_recent_samples": len(confs),
        "n_recent_images": len(logs),
        "reasons": reasons,
        "message": (
            "Model drift suspected: " + "; ".join(reasons) + ". Live images may look unlike the "
            "training data (new cameras, lighting, real photos vs. synthetic set) — consider retraining."
            if drifted
            else "Live detection behaviour is within the expected range of the training baseline."
        ),
    }


def history(db: Session, days: int = 30) -> dict:
    """Daily mean confidence / detection rate for the drift chart."""
    since = utcnow() - datetime.timedelta(days=days)
    logs = prediction_log_repository.since(db, since)
    baseline = load_baseline()

    by_day: Dict[str, List] = {}
    for row in logs:
        by_day.setdefault(row.created_at.strftime("%Y-%m-%d"), []).append(row)

    points = []
    for day in sorted(by_day):
        rows = by_day[day]
        confs = _flatten(rows)
        points.append({
            "date": day,
            "images": len(rows),
            "detections": len(confs),
            "mean_confidence": round(statistics.mean(confs), 4) if confs else None,
            "detection_rate": round(sum(1 for r in rows if r.num_detections > 0) / len(rows), 3),
        })
    return {
        "baseline_mean_confidence": baseline["mean_confidence"] if baseline else None,
        "points": points,
    }


def avg_inference_ms(db: Session, n: int = 100) -> Optional[float]:
    """Mean model forward-pass time (ms) over the last n /predict calls —
    backs the Inference Performance feature."""
    logs = prediction_log_repository.recent(db, n)
    times = [r.inference_ms for r in logs if r.inference_ms is not None]
    return round(sum(times) / len(times), 2) if times else None


def distribution(db: Session) -> dict:
    """Live (last window) vs baseline confidence histogram, for a side-by-side chart."""
    baseline = load_baseline()
    confs = _flatten(prediction_log_repository.recent(db, settings.DRIFT_WINDOW_SIZE))
    labels = [f"{i / HIST_BINS:.1f}-{(i + 1) / HIST_BINS:.1f}" for i in range(HIST_BINS)]
    return {
        "labels": labels,
        "live": analytics.proportions(analytics.histogram(confs, HIST_BINS)) if confs else [],
        "baseline": (baseline or {}).get("histogram") or [],
        "n_live": len(confs),
    }
