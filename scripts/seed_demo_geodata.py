"""Add demo GPS coordinates to existing complaints for Map/Heatmap testing.

This does not create fake complaints or alter detection results. It only fills
missing latitude/longitude/address fields on existing complaint rows.
Run from the project root after starting the backend at least once:
    python scripts/seed_demo_geodata.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal
from app.models.complaint import Complaint

DEMO_POINTS = [
    (13.0827, 80.2707, "Demo location A, Chennai"),
    (13.0674, 80.2376, "Demo location B, Chennai"),
    (13.1067, 80.2824, "Demo location C, Chennai"),
    (13.0475, 80.2090, "Demo location D, Chennai"),
]

def main():
    db = SessionLocal()
    try:
        complaints = db.query(Complaint).order_by(Complaint.date_reported.desc()).all()
        missing = [c for c in complaints if c.latitude is None or c.longitude is None]
        if not missing:
            print("All complaints already have GPS coordinates. Nothing changed.")
            return
        changed = 0
        for c, point in zip(missing, DEMO_POINTS):
            c.latitude, c.longitude, c.address = point
            changed += 1
        db.commit()
        print(f"Updated {changed} existing complaint(s) with demo coordinates.")
        print("These are demo coordinates for testing the Map/Heatmap UI; replace them with real GPS data for actual deployment.")
        if len(missing) > len(DEMO_POINTS):
            print(f"{len(missing)-len(DEMO_POINTS)} complaint(s) remain without coordinates.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
