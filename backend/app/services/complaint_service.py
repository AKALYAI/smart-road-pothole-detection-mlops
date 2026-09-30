"""
app/services/complaint_service.py
-------------------------------------
Business logic for the complaints feature:

  * turning a detection result into a saved Complaint (+ stored images),
    with duplicate detection and high-severity alerts
  * the ticket lifecycle:  Open -> Assigned -> In Progress -> Resolved
  * department assignment
  * before/after (repair photo) handling
  * read/update/delete/export used by the routers

Talks to the DB only through app.repository.* — never queries directly.
"""
import csv
import io
import json
import uuid
from typing import Optional

import cv2
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    DEPARTMENTS,
    SEVERITY_ORDER,
    STATUSES,
    allowed_next_statuses,
    can_transition,
)
from app.models.complaint import Complaint
from app.repository import complaint_repository, event_repository
from app.services import alert_service, audit_service, detection_service, drift_service, duplicate_service, email_service, zone_service
from app.services.analytics import confidence_band
from app.services.severity_service import summarize_detections
from app.utils.image_utils import draw_boxes
from app.utils.phash import dhash
from app.utils.timeutil import utcnow


# ---------------------------------------------------------------------------
# Filing a complaint from a detection result
# ---------------------------------------------------------------------------
def save_and_file_complaint(
    pil_img: Image.Image,
    annotated_bgr,
    detections: list,
    latitude: Optional[float],
    longitude: Optional[float],
    address: Optional[str],
    db: Session,
    reporter: Optional[str] = None,
    notify_email: Optional[str] = None,
    inference_ms: Optional[float] = None,
) -> dict:
    """Saves original + annotated images to disk, files a Complaint row (if
    any potholes were found and it is not a repeat of an open complaint),
    feeds the drift monitor, and returns the JSON-ready /predict result."""
    summary = summarize_detections(detections)

    uid = uuid.uuid4().hex[:10]
    orig_name = f"{uid}_orig.jpg"
    annotated_name = f"{uid}_annotated.jpg"
    pil_img.save(settings.UPLOAD_DIR / orig_name, quality=90)
    cv2.imwrite(str(settings.UPLOAD_DIR / annotated_name), annotated_bgr)

    # feed the drift monitor (persisted; counts images with zero potholes too)
    drift_service.record_prediction(db, [d["confidence"] for d in detections], inference_ms=inference_ms)

    complaint = None
    duplicate = None
    if detections:
        img_hash = dhash(pil_img)
        dup = duplicate_service.find_duplicate(db, latitude, longitude, img_hash)
        if dup:
            complaint, duplicate = _merge_duplicate(
                db, dup, summary, latitude, longitude, orig_name, reporter
            )
        else:
            zone = zone_service.find_zone_for(db, latitude, longitude)
            complaint = Complaint(
                complaint_id=uuid.uuid4().hex[:8].upper(),
                image_path=f"/uploads/{orig_name}",
                annotated_image_path=f"/uploads/{annotated_name}",
                num_potholes=len(detections),
                confidence=summary["max_confidence"],
                avg_confidence=summary["avg_confidence"],
                min_confidence=summary["min_confidence"],
                detections_json=json.dumps(detections),
                severity=summary["overall_severity"],
                latitude=latitude,
                longitude=longitude,
                address=address,
                date_reported=utcnow(),
                status="Open",
                image_hash=img_hash,
                report_count=1,
                reporter=reporter,
                notify_email=notify_email,
                inference_ms=inference_ms,
                zone_id=zone.id if zone else None,
            )
            complaint = complaint_repository.create(db, complaint)
            event_repository.add(
                db, complaint.complaint_id, "created", actor=reporter or "citizen",
                to_status="Open", note=f"Auto-filed: {complaint.num_potholes} pothole(s), {complaint.severity} severity",
            )
            alert_service.raise_if_severe(db, complaint)

    return {
        "detections": detections,
        "num_potholes": len(detections),
        "overall_severity": summary["overall_severity"],
        "max_confidence": summary["max_confidence"],
        "avg_confidence": summary["avg_confidence"],
        "confidence_band": confidence_band(summary["max_confidence"]) if detections else None,
        # top-level image URLs so the frontend can always show the
        # annotated result, even when no complaint was filed (no potholes)
        "original_image": f"/uploads/{orig_name}",
        "annotated_image": f"/uploads/{annotated_name}",
        "complaint": complaint.to_dict(public=True) if complaint else None,
        "duplicate": duplicate,   # None, or {"of": <complaint_id>, "reason": ..., ...}
    }


def _merge_duplicate(db, dup, summary, latitude, longitude, orig_name, reporter):
    """Fold a repeat report into the existing complaint instead of filing a new ticket."""
    original: Complaint = dup["complaint"]
    original.report_count = (original.report_count or 1) + 1

    escalated = SEVERITY_ORDER.get(summary["overall_severity"], 0) > SEVERITY_ORDER.get(original.severity, 0)
    if escalated:
        original.severity = summary["overall_severity"]
    if original.latitude is None and latitude is not None and longitude is not None:
        original.latitude, original.longitude = latitude, longitude  # repeat report adds GPS
    original = complaint_repository.save(db, original)

    if dup["reason"] == "same_location":
        why = f"{dup['distance_m']} m from this complaint"
    else:
        why = f"photo is near-identical ({dup['hash_distance']} bits apart)"
    event_repository.add(
        db, original.complaint_id, "duplicate_report", actor=reporter or "citizen",
        note=f"Repeat report merged — {why}. Photo: /uploads/{orig_name}"
             + (f". Severity raised to {original.severity}." if escalated else ""),
    )
    if escalated:
        alert_service.raise_if_severe(db, original, reason="Severity escalated by repeat report")

    info = {
        "of": original.complaint_id,
        "reason": dup["reason"],
        "report_count": original.report_count,
        "escalated": escalated,
    }
    info.update({k: dup[k] for k in ("distance_m", "hash_distance") if k in dup})
    return original, info


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_complaints(
    db: Session,
    severity: Optional[str],
    status: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    search: Optional[str],
    limit: int,
    offset: int,
    department: Optional[str] = None,
    reporter: Optional[str] = None,
    zone_id: Optional[int] = None,
    sort_by: str = "date_reported",
    sort_order: str = "desc",
) -> dict:
    total, complaints = complaint_repository.search(
        db, severity=severity, status=status, department=department, reporter=reporter,
        zone_id=zone_id, date_from=date_from, date_to=date_to, search_text=search,
        sort_by=sort_by, sort_order=sort_order, limit=limit, offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [c.to_dict() for c in complaints],
    }


def get_complaint_or_404(db: Session, complaint_id: str) -> Complaint:
    c = complaint_repository.get_by_complaint_id(db, complaint_id.upper())
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return c


def get_detail(db: Session, c: Complaint, public: bool = True) -> dict:
    """Complaint + timeline + which statuses it may move to next."""
    d = c.to_dict(public=public)
    d["events"] = [e.to_dict() for e in event_repository.list_for(db, c.complaint_id)]
    d["allowed_next"] = allowed_next_statuses(c.status)
    return d


# ---------------------------------------------------------------------------
# Lifecycle (admin)
# ---------------------------------------------------------------------------
def assign_department(db: Session, c: Complaint, department: str, actor: str, note: Optional[str] = None) -> Complaint:
    if department not in DEPARTMENTS:
        raise HTTPException(400, f"department must be one of {DEPARTMENTS}")
    if c.status == "Resolved":
        raise HTTPException(400, "Resolved complaints cannot be re-assigned — reopen it first.")

    prev = c.status
    c.department = department
    c.assigned_at = utcnow()
    if c.status == "Open":
        c.status = "Assigned"
    c = complaint_repository.save(db, c)
    event_repository.add(
        db, c.complaint_id, "assigned", actor=actor, from_status=prev, to_status=c.status,
        note=f"Assigned to {department}" + (f" — {note}" if note else ""),
    )
    audit_service.log(db, actor, "department_assigned", "complaint", c.complaint_id, f"-> {department}")
    return c


def change_status(db: Session, c: Complaint, new_status: str, actor: str, note: Optional[str] = None) -> Complaint:
    if new_status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    if new_status == c.status:
        return c
    if not can_transition(c.status, new_status):
        raise HTTPException(
            400,
            f"Cannot move from '{c.status}' to '{new_status}'. "
            f"Allowed: {allowed_next_statuses(c.status) or 'none'}",
        )
    if new_status in ("Assigned", "In Progress") and not c.department:
        raise HTTPException(400, "Assign a department before moving this ticket forward.")

    prev = c.status
    event_type = "status_changed"
    if new_status == "Resolved":
        c.resolved_at = utcnow()
    if new_status == "Open":
        if prev == "Resolved":
            event_type = "reopened"
            c.resolved_at = None
            c.after_image_path = c.after_annotated_path = None
            c.after_num_potholes = None
            c.resolution_note = None
        c.department = None
        c.assigned_at = None
    c.status = new_status
    c = complaint_repository.save(db, c)
    event_repository.add(
        db, c.complaint_id, event_type, actor=actor, from_status=prev, to_status=new_status, note=note,
    )
    audit_service.log(db, actor, "status_changed", "complaint", c.complaint_id, f"{prev} -> {new_status}")
    email_service.notify_status_change(c.notify_email, c.complaint_id, new_status, c.department, note)
    return c


def add_repair_photo(db: Session, c: Complaint, pil_img: Image.Image, actor: str, note: Optional[str] = None) -> Complaint:
    """Store the 'after repair' photo, re-run the model on it to verify the
    repair, and mark the ticket Resolved (if it was In Progress)."""
    if c.status not in ("In Progress", "Resolved"):
        raise HTTPException(400, "Move the ticket to 'In Progress' before uploading the repair photo.")

    uid = uuid.uuid4().hex[:10]
    after_name = f"{uid}_after.jpg"
    pil_img.save(settings.UPLOAD_DIR / after_name, quality=90)
    c.after_image_path = f"/uploads/{after_name}"
    c.after_annotated_path = None
    c.after_num_potholes = None

    verdict = "Model re-check unavailable (model not loaded)."
    if detection_service.is_model_loaded():
        detections, img_bgr, _after_inference_ms = detection_service.run_detection_on_image(pil_img)
        annotated_name = f"{uid}_after_annotated.jpg"
        cv2.imwrite(str(settings.UPLOAD_DIR / annotated_name), draw_boxes(img_bgr.copy(), detections))
        c.after_annotated_path = f"/uploads/{annotated_name}"
        c.after_num_potholes = len(detections)
        verdict = (
            "Model re-check: no potholes detected — repair verified."
            if not detections
            else f"Model re-check: {len(detections)} pothole(s) still detected — repair may be incomplete."
        )

    prev = c.status
    if c.status == "In Progress":
        c.status = "Resolved"
        c.resolved_at = utcnow()
    if note:
        c.resolution_note = note
    c = complaint_repository.save(db, c)
    event_repository.add(
        db, c.complaint_id, "repair_photo", actor=actor, from_status=prev, to_status=c.status,
        note=verdict + (f" Note: {note}" if note else ""),
    )
    audit_service.log(db, actor, "repair_photo_uploaded", "complaint", c.complaint_id, verdict)
    if c.status == "Resolved":
        email_service.notify_status_change(c.notify_email, c.complaint_id, "Resolved", c.department, note)
    return c


def correct_complaint(
    db: Session, c: Complaint, actor: str,
    corrected_severity: Optional[str] = None,
    corrected_num_potholes: Optional[int] = None,
    verified: Optional[str] = None,
    note: Optional[str] = None,
) -> Complaint:
    """Human-in-the-loop review: an admin marks a detection as correct, or
    corrects the model's severity/count. The ORIGINAL detection is kept
    untouched (for training-data audit purposes) — corrections are stored
    alongside it, and a ComplaintEvent + AuditLog record who changed what."""
    if corrected_severity and corrected_severity not in SEVERITY_ORDER:
        raise HTTPException(400, f"corrected_severity must be one of {list(SEVERITY_ORDER)}")
    if verified and verified not in ("correct", "corrected"):
        raise HTTPException(400, "verified must be 'correct' or 'corrected'")

    c.verified = verified or ("corrected" if (corrected_severity or corrected_num_potholes is not None) else "correct")
    if corrected_severity:
        c.corrected_severity = corrected_severity
    if corrected_num_potholes is not None:
        c.corrected_num_potholes = corrected_num_potholes
    c.correction_note = note
    c.corrected_by = actor
    c.corrected_at = utcnow()
    c = complaint_repository.save(db, c)

    summary_bits = []
    if corrected_severity:
        summary_bits.append(f"severity -> {corrected_severity}")
    if corrected_num_potholes is not None:
        summary_bits.append(f"potholes -> {corrected_num_potholes}")
    detail = f"{c.verified}" + (f" ({', '.join(summary_bits)})" if summary_bits else "")
    event_repository.add(db, c.complaint_id, "corrected", actor=actor, note=detail + (f" — {note}" if note else ""))
    audit_service.log(db, actor, "prediction_corrected", "complaint", c.complaint_id, detail)
    return c


def delete_complaint(db: Session, c: Complaint) -> None:
    complaint_repository.delete(db, c)


def export_csv(
    db: Session, severity: Optional[str] = None, status: Optional[str] = None,
    department: Optional[str] = None, date_from: Optional[str] = None,
    date_to: Optional[str] = None, search: Optional[str] = None,
) -> StreamingResponse:
    _, complaints = complaint_repository.search(
        db, severity=severity, status=status, department=department,
        date_from=date_from, date_to=date_to, search_text=search, limit=10000, offset=0,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "complaint_id", "num_potholes", "confidence", "avg_confidence", "severity",
        "latitude", "longitude", "address", "date_reported", "status", "department",
        "assigned_at", "resolved_at", "report_count", "after_num_potholes", "reporter",
    ])
    for c in complaints:
        writer.writerow([
            c.complaint_id, c.num_potholes, c.confidence, c.avg_confidence, c.severity,
            c.latitude, c.longitude, c.address, c.date_reported, c.status, c.department,
            c.assigned_at, c.resolved_at, c.report_count, c.after_num_potholes, c.reporter,
        ])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=roadwatch_complaints.csv"},
    )
