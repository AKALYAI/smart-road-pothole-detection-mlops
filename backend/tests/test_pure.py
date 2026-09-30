"""Framework-free unit tests: analytics, geo, hashing, passwords, lifecycle rules."""
import datetime
import io

from PIL import Image, ImageEnhance

from app.core import constants as C
from app.core.passwords import hash_password, verify_password
from app.services import analytics as A
from app.utils import geo
from app.utils.phash import dhash, hamming


def test_status_flow():
    assert C.can_transition("Open", "Assigned")
    assert C.can_transition("Assigned", "In Progress")
    assert C.can_transition("In Progress", "Resolved")
    assert not C.can_transition("Open", "Resolved")
    assert C.allowed_next_statuses("Resolved") == ["Open"]


def test_password_roundtrip():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h)
    assert not verify_password("nope", h)
    assert not verify_password("s3cret", "garbage")


def test_haversine_and_bbox():
    d = geo.haversine_m(13.0827, 80.2707, 13.0829, 80.2707)
    assert 20 < d < 25
    lo_lat, hi_lat, lo_lng, hi_lng = geo.bounding_box(13.0, 80.0, 25)
    assert lo_lat < 13.0 < hi_lat and lo_lng < 80.0 < hi_lng


def _img(seed):
    import random
    rnd = random.Random(seed)
    im = Image.new("RGB", (160, 120), (90, 90, 90))
    px = im.load()
    for x in range(160):
        for y in range(120):
            v = 90 + rnd.randint(-40, 40)
            px[x, y] = (v, v, v)
    return im


def test_dhash_same_vs_different():
    a = _img(1)
    b = ImageEnhance.Brightness(a).enhance(1.2)
    c = _img(2)
    assert hamming(dhash(a), dhash(b)) <= 12
    assert hamming(dhash(a), dhash(c)) > 12


def test_trend_series_zero_filled():
    d = datetime.datetime
    recs = [(d(2026, 9, 24, 10), "High"), (d(2026, 9, 24, 11), "Low"), (d(2026, 9, 23), "Critical")]
    t = A.trend_series(recs, "daily", 7, today=datetime.date(2026, 9, 24))
    assert len(t["points"]) == 7
    assert t["points"][-1]["total"] == 2 and t["points"][-1]["High"] == 1
    assert t["total"] == 3 and t["change_pct"] == 100.0
    w = A.trend_series(recs, "weekly", 4, today=datetime.date(2026, 9, 24))
    assert w["points"][-1]["total"] == 3
    m = A.trend_series(recs, "monthly", 3, today=datetime.date(2026, 9, 24))
    assert [p["period"] for p in m["points"]] == ["2026-07", "2026-08", "2026-09"]


def test_confidence_stats_and_bands():
    s = A.confidence_stats([
        {"confidence": 0.9, "severity": "High"},
        {"confidence": 0.6, "severity": "Medium"},
        {"confidence": 0.3, "severity": "Low"},
    ])
    assert s["bands"] == {"High": 1, "Medium": 1, "Low": 1}
    assert s["count"] == 3 and len(s["histogram"]) == 10
    assert A.confidence_band(0.7) == "High" and A.confidence_band(0.49) == "Low"


def test_hotspots_and_psi():
    pts = [{"lat": 13.0827, "lng": 80.2707, "severity": "High"},
           {"lat": 13.0828, "lng": 80.2708, "severity": "Critical"},
           {"lat": 12.9, "lng": 80.1, "severity": "Low"}]
    h = A.hotspots(pts)
    assert h[0]["complaints"] == 2 and h[0]["max_severity"] == "Critical"
    assert A.psi([0.1] * 10, [0.1] * 10) == 0
    assert A.psi([0.1] * 10, [0.02] * 5 + [0.18] * 5) > 0.25
