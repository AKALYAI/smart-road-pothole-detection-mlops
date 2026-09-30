"""
retrain_pipeline.py
---------------------
Automatic retraining pipeline: new data -> train -> evaluate -> (maybe)
promote a new model. Ties together the existing scripts instead of
duplicating their logic:

  1. scripts/generate_dataset.py   (skip with --skip-generate once you have
                                     real labeled data in data/pothole_dataset)
  2. scripts/train.py               -> trains a candidate, logs it to MLflow
  3. scripts/evaluate.py            -> measures the candidate on the test split
  4. Promotion gate: the candidate becomes models/best.pt only if its mAP50
     beats the currently-deployed model by more than --min-improvement (a
     dead-simple stand-in for a canary/shadow-traffic rollout). Otherwise
     the previous best.pt is kept and the candidate is left in runs/ for
     inspection.
  5. scripts/compute_baseline.py     -> refreshes the drift baseline so
     app/services/drift_service.py compares against the model that is
     actually serving.

Intended to be run by hand, a cron job, or the "Retrain" button described in
the README once new/real data has been added under data/pothole_dataset/.

Usage:
    python scripts/retrain_pipeline.py --epochs 30
    python scripts/retrain_pipeline.py --skip-generate --epochs 50   # real data already in place
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(cmd):
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def current_map50(model_path: Path, data_yaml: str) -> float:
    if not model_path.exists():
        return 0.0
    metrics = YOLO(str(model_path)).val(data=data_yaml, split="test", verbose=False)
    return float(metrics.results_dict.get("metrics/mAP50(B)", 0.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(REPO_ROOT / "data/pothole_dataset/data.yaml"))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--skip-generate", action="store_true", help="reuse existing data/pothole_dataset")
    ap.add_argument("--dataset-count", type=int, default=200)
    ap.add_argument("--min-improvement", type=float, default=0.0,
                     help="candidate mAP50 must beat the current model by at least this much to be promoted")
    args = ap.parse_args()

    best_path = REPO_ROOT / "models" / "best.pt"
    py = sys.executable

    if not args.skip_generate:
        run([py, "scripts/generate_dataset.py", "--count", str(args.dataset_count), "--out", "data/pothole_dataset"])

    print("\n=== Measuring currently-deployed model (if any) ===")
    before_map50 = current_map50(best_path, args.data)
    print(f"Current models/best.pt mAP50 (test split): {before_map50:.4f}")

    # back up the currently-deployed model in case the candidate is rejected
    # or something goes wrong mid-training
    backup_path = None
    if best_path.exists():
        backup_path = best_path.with_suffix(".pt.bak")
        shutil.copy(best_path, backup_path)

    print("\n=== Training candidate model ===")
    run([py, "scripts/train.py", "--data", args.data, "--epochs", str(args.epochs), "--imgsz", str(args.imgsz)])
    # scripts/train.py just overwrote models/best.pt with the NEW candidate

    print("\n=== Evaluating candidate ===")
    run([py, "scripts/evaluate.py", "--data", args.data, "--split", "test"])
    after_map50 = current_map50(best_path, args.data)
    print(f"Candidate mAP50 (test split): {after_map50:.4f}")

    improvement = after_map50 - before_map50
    promoted = improvement >= args.min_improvement
    print(f"\n=== Promotion decision: {'PROMOTE' if promoted else 'REJECT'} "
          f"(delta {improvement:+.4f}, need >= {args.min_improvement:+.4f}) ===")

    if not promoted and backup_path is not None:
        shutil.copy(backup_path, best_path)
        print(f"Restored previous model — models/best.pt unchanged (mAP50 {before_map50:.4f}).")
    elif promoted:
        print(f"models/best.pt is now the new candidate (mAP50 {after_map50:.4f}). "
              f"Restart the backend (or redeploy) to load it.")

    if backup_path is not None:
        backup_path.unlink(missing_ok=True)

    print("\n=== Refreshing drift baseline against the deployed model ===")
    run([py, "scripts/compute_baseline.py", "--model", str(best_path), "--data", args.data, "--split", "val"])

    print("\nDone. See app/routers/models_router.py (GET /models/versions) to compare this run against past ones.")


if __name__ == "__main__":
    main()
