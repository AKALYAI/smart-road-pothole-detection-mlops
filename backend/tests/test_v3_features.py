"""End-to-end tests for the v2.1 additions: reports, model performance,
email notify, zones/road health, human-in-the-loop corrections, audit log,
and dataset management. Same fake-detector setup as test_api.py."""
import io

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("reportlab")
pytest.importorskip("openpyxl")
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
        det = [{"class": "pothole", "confidence": 0.83, "confidence_band": "High",
                "box": [5, 5, 50, 50], "severity": "High"}]
        import cv2
        return det, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR), 9.4
    monkeypatch.setattr(detection_service, "is_model_loaded", lambda: True)
    monkeypatch.setattr(detection_service, "run_detection_on_image", fake)


def _admin(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "test-admin-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_zone_auto_assign_and_health_score(client):
    admin = _admin(client)

    r = client.post("/zones", data={"name": "Ward Test Zone", "latitude": "13.0827",
                                     "longitude": "80.2707", "radius_km": "1.5"}, headers=admin)
    assert r.status_code == 200, r.text
    zone_id = r.json()["id"]

    # a complaint inside the zone's radius should be auto-assigned
    r = client.post("/predict", files={"file": ("z.jpg", _photo(10), "image/jpeg")},
                     data={"latitude": "13.0830", "longitude": "80.2710"})
    cid = r.json()["complaint"]["complaint_id"]
    detail = client.get(f"/complaints/{cid}").json()
    assert detail["zone_id"] == zone_id

    zones = client.get("/zones").json()["zones"]
    match = next(z for z in zones if z["id"] == zone_id)
    assert match["total_complaints"] >= 1
    assert 0 <= match["score"] <= 100

    detail_view = client.get(f"/zones/{zone_id}").json()
    assert detail_view["total_complaints"] >= 1
    assert any(c["complaint_id"] == cid for c in detail_view["complaints"])


def test_reports_and_advanced_filters(client):
    admin = _admin(client)
    r = client.post("/predict", files={"file": ("r.jpg", _photo(11), "image/jpeg")})
    assert r.status_code == 200

    csv_r = client.get("/complaints/export.csv", headers=admin)
    assert csv_r.status_code == 200 and csv_r.headers["content-type"].startswith("text/csv")

    pdf_r = client.get("/complaints/export.pdf?severity=High", headers=admin)
    assert pdf_r.status_code == 200 and pdf_r.headers["content-type"] == "application/pdf"

    xlsx_r = client.get("/complaints/export.xlsx", headers=admin)
    assert xlsx_r.status_code == 200
    assert "spreadsheetml" in xlsx_r.headers["content-type"]

    # exports require admin
    assert client.get("/complaints/export.pdf").status_code == 401

    # multi-severity filter + sorting
    listed = client.get("/complaints?severity=High,Critical&sort_by=confidence&sort_order=asc",
                         headers=admin).json()
    assert listed["total"] >= 1


def test_human_in_the_loop_correction(client):
    admin = _admin(client)
    r = client.post("/predict", files={"file": ("c.jpg", _photo(12), "image/jpeg")})
    cid = r.json()["complaint"]["complaint_id"]

    # non-admin cannot correct
    citizen = client.post("/auth/register", json={"username": "correcter1", "password": "secret1"}).json()
    h = {"Authorization": f"Bearer {citizen['access_token']}"}
    assert client.patch(f"/complaints/{cid}/correct", data={"verified": "correct"}, headers=h).status_code == 403

    r = client.patch(f"/complaints/{cid}/correct",
                      data={"corrected_severity": "Critical", "corrected_num_potholes": "3", "note": "reviewed"},
                      headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] == "corrected"
    assert body["corrected_severity"] == "Critical"
    assert body["corrected_num_potholes"] == 3
    assert any(e["event_type"] == "corrected" for e in body["events"])


def test_audit_log_records_admin_actions(client):
    admin = _admin(client)
    client.post("/zones", data={"name": "Audit Test Zone", "latitude": "13.10",
                                 "longitude": "80.20", "radius_km": "1"}, headers=admin)
    logs = client.get("/audit?action=zone_created", headers=admin).json()
    assert logs["total"] >= 1
    assert logs["items"][0]["action"] == "zone_created"

    # non-admin blocked
    citizen = client.post("/auth/register", json={"username": "auditor1", "password": "secret1"}).json()
    h = {"Authorization": f"Bearer {citizen['access_token']}"}
    assert client.get("/audit", headers=h).status_code == 403


def test_model_performance_and_dataset_upload(client):
    admin = _admin(client)
    perf = client.get("/models/performance", headers=admin)
    assert perf.status_code == 200
    body = perf.json()
    assert "metrics" in body and "avg_inference_ms" in body

    up = client.post("/dataset/images", files={"file": ("train1.jpg", _photo(20), "image/jpeg")},
                      data={"notes": "test upload"}, headers=admin)
    assert up.status_code == 200, up.text
    img_id = up.json()["id"]
    assert up.json()["has_label"] is False

    listed = client.get("/dataset/images", headers=admin).json()
    assert listed["total"] >= 1

    assert client.delete(f"/dataset/images/{img_id}", headers=admin).status_code == 200


def test_registration_with_email_and_update(client):
    r = client.post("/auth/register", json={"username": "emailuser1", "password": "secret1", "email": "not-an-email"})
    assert r.status_code == 400

    r = client.post("/auth/register", json={"username": "emailuser2", "password": "secret1", "email": "a@b.com"})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=h).json()["username"] == "emailuser2"

    r2 = client.patch("/auth/me/email", params={"email": "new@b.com"}, headers=h)
    assert r2.status_code == 200 and r2.json()["email"] == "new@b.com"
