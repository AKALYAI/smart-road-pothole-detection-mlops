"""
train.py
--------
Trains a YOLOv8 object-detection model on the pothole dataset and logs
every run (parameters, metrics per epoch, and model artifacts) to MLflow.
The best checkpoint is copied to models/best.pt for the FastAPI backend.

Usage:
    python scripts/train.py --epochs 30 --imgsz 640 --model yolov8n.pt
"""
import argparse
import hashlib
import re
import shutil
from pathlib import Path

import mlflow
import yaml
from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(REPO_ROOT / "data/pothole_dataset/data.yaml"))
    ap.add_argument("--model", default="yolov8n.pt", help="base weights to fine-tune from")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--experiment", default="pothole-detection")
    ap.add_argument("--run_name", default=None)
    args = ap.parse_args()

    mlflow.set_tracking_uri(f"sqlite:///{REPO_ROOT / 'mlflow_tracking' / 'mlflow.db'}")
    mlflow.set_experiment(args.experiment)

    with mlflow.start_run(run_name=args.run_name):
        mlflow.log_params(
            {
                "base_model": args.model,
                "epochs": args.epochs,
                "imgsz": args.imgsz,
                "batch": args.batch,
                "data_yaml": args.data,
            }
        )

        model = YOLO(args.model)

        results = model.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            project=str(REPO_ROOT / "runs"),
            name="pothole_train",
            exist_ok=True,
            verbose=False,
            plots=True,
        )

        # ---- pull final epoch metrics out of the results object ----
        metrics = {}
        try:
            rd = results.results_dict
            metrics = {
                "precision": rd.get("metrics/precision(B)", 0.0),
                "recall": rd.get("metrics/recall(B)", 0.0),
                "mAP50": rd.get("metrics/mAP50(B)", 0.0),
                "mAP50-95": rd.get("metrics/mAP50-95(B)", 0.0),
                "box_loss": rd.get("val/box_loss", 0.0),
                "cls_loss": rd.get("val/cls_loss", 0.0),
            }
        except Exception as e:
            print("Could not parse results_dict:", e)

        # also log the full per-epoch curve from results.csv, if present
        csv_path = REPO_ROOT / "runs/pothole_train/results.csv"
        if csv_path.exists():
            import csv as _csv
            with open(csv_path) as f:
                reader = _csv.DictReader(f)
                for i, row in enumerate(reader):
                    step_metrics = {}
                    for k, v in row.items():
                        k = k.strip()
                        # sanitize to mlflow-safe metric name: alnum, _, -, ., space, :, /
                        safe_k = re.sub(r"[^A-Za-z0-9_\-. :/]", "", k.replace("(B)", ""))
                        try:
                            step_metrics[safe_k] = float(v)
                        except (TypeError, ValueError):
                            pass
                    if step_metrics:
                        mlflow.log_metrics(step_metrics, step=i)

        if metrics:
            mlflow.log_metrics(metrics)

        # ---- promote best.pt ----
        best_src = REPO_ROOT / "runs/pothole_train/weights/best.pt"
        models_dir = REPO_ROOT / "models"
        models_dir.mkdir(exist_ok=True)
        best_dst = models_dir / "best.pt"
        if best_src.exists():
            shutil.copy(best_src, best_dst)
            mlflow.log_artifact(str(best_dst), artifact_path="model")
            # lets the API's /models/versions mark which run is currently serving
            sha = hashlib.sha256(best_dst.read_bytes()).hexdigest()
            mlflow.set_tag("model_sha256", sha)
            print(f"Best model saved to {best_dst}")
        else:
            print("WARNING: best.pt not found — training may have failed.")

        # log dataset config for reproducibility
        mlflow.log_artifact(args.data, artifact_path="dataset_config")

        print("Final metrics:", metrics)
        print(f"MLflow run logged under experiment '{args.experiment}'")


if __name__ == "__main__":
    main()
