"""
app/routers/complaints_router.py
-------------------------------------
GET    /complaints                     — list complaints (paginated, filterable, sortable)  [admin]
GET    /complaints/export.csv          — download filtered complaints as CSV                 [admin]
GET    /complaints/export.pdf          — download filtered complaints as a PDF report          [admin]
GET    /complaints/export.xlsx         — download filtered complaints as an Excel report        [admin]
GET    /complaints/mine                — complaints filed by the logged-in citizen             [login]
GET    /complaints/{id}                — get one complaint + timeline                          [public — citizen tracking]
PATCH  /complaints/{id}/status         — change status (Open/Assigned/In Progress/Resolved)    [login]
PATCH  /complaints/{id}/assign         — assign to a department                                [admin]
PATCH  /complaints/{id}/correct        — human-in-the-loop: verify/correct the model's call     [admin]
POST   /complaints/{id}/after-image    — upload after-repair photo, auto-verify, resolve         [admin]
DELETE /complaints/{id}                — delete a complaint                                     [API key]

See app/routers/meta_router.py for GET /departments and GET /statuses.
"""
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin, require_user, verify_api_key
from app.db.session import get_db
from app.services import complaint_service, report_service

router = APIRouter(tags=["Complaints"])


@router.get("/complaints")
def list_complaints(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
    severity: Optional[str] = Query(None, description="Filter: Low/Medium/High/Critical, or comma-separated for several"),
    status: Optional[str] = Query(None, description="Filter: Open/Assigned/In Progress/Resolved"),
    department: Optional[str] = Query(None),
    zone_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date, e.g. 2026-01-01"),
    date_to: Optional[str] = Query(None, description="ISO date, e.g. 2026-12-31"),
    search: Optional[str] = Query(None, description="Search complaint ID or address"),
    sort_by: str = Query("date_reported", pattern="^(date_reported|severity|status|confidence|num_potholes)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return complaint_service.list_complaints(
        db, severity=severity, status=status, department=department, zone_id=zone_id,
        date_from=date_from, date_to=date_to, search=search,
        sort_by=sort_by, sort_order=sort_order, limit=limit, offset=offset,
    )


@router.get("/complaints/export.csv")
def export_complaints_csv(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    return complaint_service.export_csv(
        db, severity=severity, status=status, department=department,
        date_from=date_from, date_to=date_to, search=search,
    )


@router.get("/complaints/export.pdf")
def export_complaints_pdf(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    return report_service.generate_pdf(
        db, severity=severity, status=status, department=department,
        date_from=date_from, date_to=date_to, search=search,
    )


@router.get("/complaints/export.xlsx")
def export_complaints_excel(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    return report_service.generate_excel(
        db, severity=severity, status=status, department=department,
        date_from=date_from, date_to=date_to, search=search,
    )


@router.get("/complaints/mine")
def my_complaints(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Complaints filed by the logged-in citizen while authenticated
    (anonymous reports are not linked to any account)."""
    return complaint_service.list_complaints(
        db, severity=None, status=None, department=None, reporter=user.username,
        date_from=None, date_to=None, search=None, limit=limit, offset=offset,
    )


@router.get("/complaints/{complaint_id}")
def get_complaint(complaint_id: str, db: Session = Depends(get_db)):
    c = complaint_service.get_complaint_or_404(db, complaint_id)
    return complaint_service.get_detail(db, c, public=True)


@router.patch("/complaints/{complaint_id}/status")
def update_status(
    complaint_id: str,
    status: str = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_user),
):
    c = complaint_service.get_complaint_or_404(db, complaint_id)
    c = complaint_service.change_status(db, c, status, actor=user.username, note=note)
    return complaint_service.get_detail(db, c, public=True)


@router.patch("/complaints/{complaint_id}/assign")
def assign_department(
    complaint_id: str,
    department: str = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    c = complaint_service.get_complaint_or_404(db, complaint_id)
    c = complaint_service.assign_department(db, c, department, actor=user.username, note=note)
    return complaint_service.get_detail(db, c, public=True)


@router.patch("/complaints/{complaint_id}/correct")
def correct_complaint(
    complaint_id: str,
    verified: Optional[str] = Form(None, description="'correct' or 'corrected'"),
    corrected_severity: Optional[str] = Form(None),
    corrected_num_potholes: Optional[int] = Form(None),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    """Human-in-the-Loop: an admin confirms a detection was right, or
    supplies the correct severity/pothole count when the model got it
    wrong. Kept separate from the original detection fields so the raw
    model output stays available for later error analysis."""
    c = complaint_service.get_complaint_or_404(db, complaint_id)
    c = complaint_service.correct_complaint(
        db, c, actor=user.username, corrected_severity=corrected_severity,
        corrected_num_potholes=corrected_num_potholes, verified=verified, note=note,
    )
    return complaint_service.get_detail(db, c, public=True)


@router.post("/complaints/{complaint_id}/after-image")
async def upload_repair_photo(
    complaint_id: str,
    file: UploadFile = File(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    contents = await file.read()
    try:
        pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")
    c = complaint_service.get_complaint_or_404(db, complaint_id)
    c = complaint_service.add_repair_photo(db, c, pil_img, actor=user.username, note=note)
    return complaint_service.get_detail(db, c, public=True)


@router.delete("/complaints/{complaint_id}", dependencies=[Depends(verify_api_key)])
def delete_complaint(complaint_id: str, db: Session = Depends(get_db)):
    c = complaint_service.get_complaint_or_404(db, complaint_id)
    complaint_service.delete_complaint(db, c)
    return {"deleted": complaint_id}
