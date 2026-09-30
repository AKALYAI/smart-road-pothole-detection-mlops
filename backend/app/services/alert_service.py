"""
app/services/alert_service.py
--------------------------------
High-severity alerts. Whenever a NEW complaint is filed (or an existing one
is escalated) at High/Critical severity we:
  1. store an Alert row  -> shown in the admin dashboard (bell + Alerts tab)
  2. optionally POST a JSON payload to ALERT_WEBHOOK_URL (best effort,
     background thread, never blocks or breaks the request).
"""
import json
import threading
import urllib.request
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import Alert
from app.models.complaint import Complaint
from app.repository import alert_repository


def _post_webhook(payload: dict) -> None:
    url = settings.ALERT_WEBHOOK_URL
    if not url:
        return
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:  # noqa: BLE001 — alert delivery must never crash a request
        print(f"[alert] webhook delivery failed: {e}")


def raise_if_severe(db: Session, complaint: Complaint, reason: str = "New pothole reported") -> Optional[Alert]:
    if complaint.severity not in settings.ALERT_SEVERITIES:
        return None

    where = (
        f"{complaint.latitude:.5f}, {complaint.longitude:.5f}"
        if complaint.latitude is not None and complaint.longitude is not None
        else (complaint.address or "location unknown")
    )
    message = (
        f"{complaint.severity} pothole — {reason} "
        f"(#{complaint.complaint_id}, {complaint.num_potholes} detected, at {where})"
    )
    alert = alert_repository.create(db, complaint.complaint_id, complaint.severity, message)

    if settings.ALERT_WEBHOOK_URL:
        payload = {"text": f"🚨 {message}", "alert": alert.to_dict()}
        threading.Thread(target=_post_webhook, args=(payload,), daemon=True).start()
    return alert


def list_alerts(db: Session, unread_only: bool = False) -> List[dict]:
    return [a.to_dict() for a in alert_repository.list_alerts(db, unread_only=unread_only)]
