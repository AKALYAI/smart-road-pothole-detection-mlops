"""
evaluate.py
-----------
Evaluates the trained model (models/best.pt) on the held-out test split,
and optionally on a folder of external/real-world images that were never
part of training or validation. Prints standard detection metrics for the
test split and per-image detection summaries for the external folder so
you can eyeball real-world performance.

Usage:
    # Evaluate on the held-out test split defined in data.yaml
    python scripts/evaluate.py --split test

    # Additionally run inference on external, unseen images
    python scripts/evaluate.py --split test --external_dir path/to/real_world_images
"""
import argparse
import json
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(REPO_ROOT / "models" / "best.pt"))
    ap.add_argument("--data", default=str(REPO_ROOT / "data/pothole_dataset/data.yaml"))
    ap.add_argument("--split", default="test", choices=["train", "val", "test"])
    ap.add_argument("--external_dir", default=None, help="Folder of extra real-world images to sanity-check")
    ap.add_argument("--conf", type=float, default=0.25)
    args = ap.parse_args()

    model = YOLO(args.model)

    print(f"\n=== Evaluating on '{args.split}' split (held-out / unseen during training) ===")
    metrics = model.val(data=args.data, split=args.split, conf=args.conf, verbose=True)
    summary = {
        "precision": float(metrics.results_dict.get("metrics/precision(B)", 0.0)),
        "recall": float(metrics.results_dict.get("metrics/recall(B)", 0.0)),
        "mAP50": float(metrics.results_dict.get("metrics/mAP50(B)", 0.0)),
        "mAP50-95": float(metrics.results_dict.get("metrics/mAP50-95(B)", 0.0)),
    }
    print(f"\nTest-split summary: {json.dumps(summary, indent=2)}")

    if args.external_dir:
        ext_dir = Path(args.external_dir)
        images = sorted([p for p in ext_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
        print(f"\n=== Running inference on {len(images)} external / real-world images from {ext_dir} ===")
        results = model.predict(source=[str(p) for p in images], conf=args.conf, verbose=False)
        for img_path, r in zip(images, results):
            n = len(r.boxes)
            confs = [round(float(c), 3) for c in r.boxes.conf] if n else []
            print(f"  {img_path.name}: {n} pothole(s) detected, confidences={confs}")

    print("\nDone. See runs/ for saved plots (confusion matrix, PR curve, etc.) from the val() call.")


if __name__ == "__main__":
    main()
