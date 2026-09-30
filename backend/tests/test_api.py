"""End-to-end API tests (need fastapi/httpx/ultralytics installed — run in CI).
The YOLO model is replaced by a fake detector so no weights are required."""
import io

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import detection_service  # noqa: E402


def _photo(seed=0):
    rng = np.random.default_rng(seed)
    arr = rng.integers(60, 140, (120, 160, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fake_detector(monkeypatch):
    def fake(pil_img):
        det = [{"class": "pothole", "confidence": 0.9, "confidence_band": "High",
                "box": [10, 10, 100, 100], "severity": "Critical"}]
        import cv2
        return det, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR), 12.3
    monkeypatch.setattr(detection_service, "is_model_loaded", lambda: True)
    monkeypatch.setattr(detection_service, "run_detection_on_image", fake)


def _admin(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "test-admin-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_endpoints_require_login(client):
    assert client.get("/complaints").status_code == 401
    assert client.get("/alerts").status_code == 401
    citizen = client.post("/auth/register", json={"username": "asha", "password": "secret1"}).json()
    h = {"Authorization": f"Bearer {citizen['access_token']}"}
    assert client.get("/complaints", headers=h).status_code == 403


def test_full_lifecycle_duplicates_alerts(client):
    admin = _admin(client)

    # 1) new report with GPS -> new complaint + critical alert
    r = client.post("/predict", files={"file": ("a.jpg", _photo(1), "image/jpeg")},
                    data={"latitude": "13.0827", "longitude": "80.2707"})
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body["complaint"]["complaint_id"]
    assert body["duplicate"] is None
    assert client.get("/alerts/unread-count", headers=admin).json()["unread"] >= 1

    # 2) second report ~10 m away -> merged as duplicate
    r = client.post("/predict", files={"file": ("b.jpg", _photo(2), "image/jpeg")},
                    data={"latitude": "13.08279", "longitude": "80.2707"})
    dup = r.json()["duplicate"]
    assert dup and dup["of"] == cid and dup["report_count"] == 2

    # 3) lifecycle rules
    assert client.patch(f"/complaints/{cid}/status", data={"status": "Resolved"}, headers=admin).status_code == 400
    assert client.patch(f"/complaints/{cid}/status", data={"status": "Assigned"}, headers=admin).status_code == 400  # no dept yet
    r = client.patch(f"/complaints/{cid}/assign", data={"department": "Municipal Corporation"}, headers=admin)
    assert r.json()["status"] == "Assigned"
    r = client.patch(f"/complaints/{cid}/status", data={"status": "In Progress"}, headers=admin)
    assert r.json()["status"] == "In Progress"

    # 4) repair photo resolves it (fake detector still "sees" a pothole -> flagged)
    r = client.post(f"/complaints/{cid}/after-image", files={"file": ("after.jpg", _photo(3), "image/jpeg")},
                    headers=admin)
    j = r.json()
    assert j["status"] == "Resolved" and j["after_image_path"]

    # 5) public tracking shows the timeline, no reporter
    pub = client.get(f"/complaints/{cid}").json()
    assert "reporter" not in pub
    kinds = [e["event_type"] for e in pub["events"]]
    assert kinds[0] == "created" and "duplicate_report" in kinds and "repair_photo" in kinds


def test_analytics_endpoints(client):
    admin = _admin(client)
    assert client.get("/insights", headers=admin).status_code == 200
    assert client.get("/insights/trends?period=weekly", headers=admin).status_code == 200
    assert client.get("/insights/confidence", headers=admin).status_code == 200
    assert client.get("/insights/hotspots", headers=admin).status_code == 200
    assert client.get("/insights/map").status_code == 200          # public
    assert client.get("/drift", headers=admin).status_code == 200
    assert client.get("/models/versions", headers=admin).status_code == 200
