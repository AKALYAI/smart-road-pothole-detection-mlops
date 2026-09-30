"""
app/core/constants.py
----------------------
Pure constants + tiny helpers shared across the app (no framework imports,
so they are trivially unit-testable).
"""
from typing import List

# ---- Severity ----------------------------------------------------------
SEVERITY_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
SEVERITIES = list(SEVERITY_ORDER.keys())
# weight used by the heatmap (a Critical pothole "burns" hotter than a Low one)
SEVERITY_WEIGHT = {"Low": 0.25, "Medium": 0.5, "High": 0.75, "Critical": 1.0}

# ---- Complaint lifecycle ---------------------------------------------------
# Open -> Assigned -> In Progress -> Resolved   (+ reopen: Resolved -> Open)
STATUSES = ["Open", "Assigned", "In Progress", "Resolved"]

_TRANSITIONS = {
    "Open": ["Assigned"],
    "Assigned": ["In Progress", "Open"],
    "In Progress": ["Resolved", "Assigned"],
    "Resolved": ["Open"],  # reopen if the repair failed / pothole came back
}

# ---- Departments a complaint can be routed to -----------------------------------
DEPARTMENTS = [
    "Roads & Highways Department",
    "Municipal Corporation",
    "Public Works Department (PWD)",
    "National Highways Authority",
]

# ---- Model confidence bands (detection quality) ---------------------------------
CONF_HIGH = 0.70
CONF_MEDIUM = 0.50


def allowed_next_statuses(current: str) -> List[str]:
    """Statuses a complaint may move to from `current`."""
    return list(_TRANSITIONS.get(current, []))


def can_transition(current: str, new: str) -> bool:
    return new in _TRANSITIONS.get(current, [])
