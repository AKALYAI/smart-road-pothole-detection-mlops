"""GET /departments, GET /statuses — lookup lists for the UI."""
from fastapi import APIRouter

from app.core.constants import DEPARTMENTS, STATUSES, allowed_next_statuses

router = APIRouter(tags=["Meta"])


@router.get("/departments")
def departments():
    return DEPARTMENTS


@router.get("/statuses")
def statuses():
    return {"statuses": STATUSES, "transitions": {s: allowed_next_statuses(s) for s in STATUSES}}
