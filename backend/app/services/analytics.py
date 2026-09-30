"""
app/services/analytics.py
---------------------------
PURE analytics helpers (no DB, no framework): trend bucketing, confidence
statistics, hotspot grouping and the Population Stability Index used for
drift. Keeping them pure makes them easy to unit-test — see tests/.
"""
import datetime
import math
import statistics
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.constants import (
    CONF_HIGH,
    CONF_MEDIUM,
    SEVERITIES,
    SEVERITY_ORDER,
    SEVERITY_WEIGHT,
)


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------
def confidence_band(conf: float) -> str:
    """Detection-quality label for a single confidence score."""
    if conf >= CONF_HIGH:
        return "High"
    if conf >= CONF_MEDIUM:
        return "Medium"
    return "Low"


def histogram(values: Iterable[float], bins: int = 10, lo: float = 0.0, hi: float = 1.0) -> List[int]:
    counts = [0] * bins
    width = (hi - lo) / bins
    for v in values:
        idx = int((v - lo) / width)
        counts[max(0, min(bins - 1, idx))] += 1
    return counts


def proportions(counts: Sequence[int]) -> List[float]:
    total = sum(counts)
    return [c / total for c in counts] if total else [0.0] * len(counts)


def confidence_stats(detections: Sequence[dict], bins: int = 10) -> dict:
    """detections: [{"confidence": float, "severity": str}, ...]"""
    confs = [float(d["confidence"]) for d in detections]
    if not confs:
        return {"count": 0, "histogram": [], "bands": {"High": 0, "Medium": 0, "Low": 0}, "by_severity": {}}

    counts = histogram(confs, bins)
    width = 1.0 / bins
    hist = [
        {"range": f"{i * width:.1f}-{(i + 1) * width:.1f}", "count": c} for i, c in enumerate(counts)
    ]
    bands = {"High": 0, "Medium": 0, "Low": 0}
    for c in confs:
        bands[confidence_band(c)] += 1

    by_sev: Dict[str, dict] = {}
    for sev in SEVERITIES:
        vals = [float(d["confidence"]) for d in detections if d.get("severity") == sev]
        if vals:
            by_sev[sev] = {"count": len(vals), "mean": round(statistics.mean(vals), 4)}

    return {
        "count": len(confs),
        "mean": round(statistics.mean(confs), 4),
        "median": round(statistics.median(confs), 4),
        "std": round(statistics.pstdev(confs), 4),
        "min": round(min(confs), 4),
        "max": round(max(confs), 4),
        "histogram": hist,
        "bands": bands,
        "by_severity": by_sev,
    }


# --------------------------------------------------------------------------
# Trends
# --------------------------------------------------------------------------
def _month_start(d: datetime.date, back: int) -> datetime.date:
    """First day of the month `back` months before d's month."""
    idx = d.year * 12 + (d.month - 1) - back
    return datetime.date(idx // 12, idx % 12 + 1, 1)


def _empty_point(label: str) -> dict:
    p = {"period": label, "total": 0}
    p.update({s: 0 for s in SEVERITIES})
    return p


def trend_series(
    records: Iterable[Tuple[datetime.datetime, Optional[str]]],
    period: str = "daily",
    periods: Optional[int] = None,
    today: Optional[datetime.date] = None,
) -> dict:
    """Complaint counts bucketed by day / ISO-week (Monday start) / month,
    zero-filled so charts have no gaps, split by severity, with a moving
    average and a last-vs-previous comparison."""
    if period not in ("daily", "weekly", "monthly"):
        raise ValueError("period must be daily, weekly or monthly")
    today = today or datetime.date.today()
    periods = periods or {"daily": 30, "weekly": 12, "monthly": 12}[period]

    if period == "daily":
        starts = [today - datetime.timedelta(days=i) for i in range(periods - 1, -1, -1)]
        key_of = lambda d: d
        label_of = lambda d: d.isoformat()
    elif period == "weekly":
        this_monday = today - datetime.timedelta(days=today.weekday())
        starts = [this_monday - datetime.timedelta(weeks=i) for i in range(periods - 1, -1, -1)]
        key_of = lambda d: d - datetime.timedelta(days=d.weekday())
        label_of = lambda d: d.isoformat()  # Monday of that week
    else:
        starts = [_month_start(today, i) for i in range(periods - 1, -1, -1)]
        key_of = lambda d: datetime.date(d.year, d.month, 1)
        label_of = lambda d: d.strftime("%Y-%m")

    points = {s: _empty_point(label_of(s)) for s in starts}
    for dt, sev in records:
        if dt is None:
            continue
        k = key_of(dt.date())
        if k in points:
            points[k]["total"] += 1
            if sev in SEVERITY_ORDER:
                points[k][sev] += 1

    series = [points[s] for s in starts]
    window = 7 if period == "daily" else 3
    for i, p in enumerate(series):
        chunk = series[max(0, i - window + 1): i + 1]
        p["moving_avg"] = round(sum(c["total"] for c in chunk) / len(chunk), 2)

    last = series[-1]["total"] if series else 0
    prev = series[-2]["total"] if len(series) > 1 else 0
    change = round((last - prev) / prev * 100, 1) if prev else None
    peak = max(series, key=lambda p: p["total"]) if series else None

    return {
        "period": period,
        "points": series,
        "total": sum(p["total"] for p in series),
        "change_pct": change,  # last bucket vs the one before (None if previous was 0)
        "peak": {"period": peak["period"], "total": peak["total"]} if peak and peak["total"] else None,
    }


# --------------------------------------------------------------------------
# Hotspots (grid clustering) — "pothole-prone areas"
# --------------------------------------------------------------------------
def hotspots(points: Iterable[dict], cell_deg: float = 0.005, top: int = 10) -> List[dict]:
    """points: [{"lat","lng","severity"}]. ~0.005 deg is roughly a 550 m grid."""
    cells: Dict[Tuple[int, int], dict] = {}
    for p in points:
        key = (math.floor(p["lat"] / cell_deg), math.floor(p["lng"] / cell_deg))
        c = cells.setdefault(key, {"lat_sum": 0.0, "lng_sum": 0.0, "n": 0, "score": 0.0, "max_sev": "Low"})
        c["lat_sum"] += p["lat"]
        c["lng_sum"] += p["lng"]
        c["n"] += 1
        sev = p.get("severity") or "Low"
        c["score"] += SEVERITY_WEIGHT.get(sev, 0.25)
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(c["max_sev"], 0):
            c["max_sev"] = sev

    out = [
        {
            "lat": round(c["lat_sum"] / c["n"], 6),
            "lng": round(c["lng_sum"] / c["n"], 6),
            "complaints": c["n"],
            "score": round(c["score"], 2),
            "max_severity": c["max_sev"],
        }
        for c in cells.values()
    ]
    out.sort(key=lambda h: (h["score"], h["complaints"]), reverse=True)
    return out[:top]


# --------------------------------------------------------------------------
# Drift math
# --------------------------------------------------------------------------
def psi(expected: Sequence[float], actual: Sequence[float], eps: float = 1e-4) -> float:
    """Population Stability Index between two binned proportion vectors.
    <0.1 stable, 0.1-0.25 moderate shift, >0.25 significant shift."""
    total = 0.0
    for e, a in zip(expected, actual):
        e, a = max(e, eps), max(a, eps)
        total += (a - e) * math.log(a / e)
    return round(total, 4)
