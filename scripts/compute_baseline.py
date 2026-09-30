"""
compute_baseline.py
--------------------
Runs the trained model over the training-time validation split and writes
models/baseline_stats.json — the reference distribution that
app/services/drift_service.py compares live traffic against.

Usage:
    python scripts/compute_baseline.py --split val
"""
import argparse
import json
import statistics
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent
HIST_BINS = 10


def histogram_proportions(values, bins=HIST_BINS):
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, max(0, int(v * bins)))
        counts[idx] += 1
    total = sum(counts) or 1
    return [c / total for c in counts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(REPO_ROOT / "models" / "best.pt"))
    ap.add_argument("--data", default=str(REPO_ROOT / "data/pothole_dataset/data.yaml"))
    ap.add_argument("--split", default="val", choices=["train", "val", "test"])
    ap.add_argument("--conf", type=float, default=0.25)
    args = ap.parse_args()

    model = YOLO(args.model)

    import yaml
    data_cfg = yaml.safe_load(open(args.data))
    split_dir = Path(args.data).parent / data_cfg[args.split]
    images = sorted([p for p in split_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if not images:
        raise SystemExit(f"No images found in {split_dir}")

    results = model.predict(source=[str(p) for p in images], conf=args.conf, verbose=False)
    confs = [float(c) for r in results for c in r.boxes.conf]
    images_with_detection = sum(1 for r in results if len(r.boxes) > 0)

    if not confs:
        raise SystemExit("No detections found on the baseline split — check --conf / the model.")

    stats = {
        "mean_confidence": statistics.mean(confs),
        "std_confidence": statistics.pstdev(confs) if len(confs) > 1 else 0.0,
        "n_detections": len(confs),
        "histogram": histogram_proportions(confs),
        "detection_rate": images_with_detection / len(images),
    }
    out_path = REPO_ROOT / "models" / "baseline_stats.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Baseline written to {out_path}:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
