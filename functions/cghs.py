import os
import json

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cghs_rates.json")
_db = None

def _load() -> dict:
    global _db
    if _db is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _db = raw.get("departments", raw)   # handle both schema versions
    return _db


def get_cost_estimate(department: str) -> dict | None:
    """
    Returns OPD consultation cost range + CGHS benchmark rate for a department.
    No network call — always local.

    Returns:
    {
      "opd_min": int,
      "opd_max": int,
      "cghs_rate": int,
      "display": "₹300–800 OPD consultation",
      "cghs_display": "CGHS rate: ₹350",
      "source": "CGHS 2024 Rate Card + Mumbai private hospital averages"
    }

    Returns None if department unknown or file missing — UI hides cost section.
    """
    if not department or not department.strip():
        return None
    try:
        db = _load()
    except Exception:
        return None

    dept = db.get(department)
    if not dept:
        return None

    opd = dept["opd_consultation"]
    return {
        "opd_min":     opd["min"],
        "opd_max":     opd["max"],
        "cghs_rate":   dept["cghs_rate"],
        "display":     f"₹{opd['min']}–{opd['max']} OPD consultation",
        "cghs_display": f"CGHS rate: ₹{dept['cghs_rate']}",
        "source":      "CGHS 2024 Rate Card + Mumbai private hospital averages",
    }


def get_procedures(department: str) -> dict:
    """
    Returns the common_procedures dict for a department.
    Each key is a procedure name, value is {"min", "max", "cghs"}.
    Returns {} if department unknown or file missing.
    """
    if not department or not department.strip():
        return {}
    try:
        db = _load()
    except Exception:
        return {}
    dept = db.get(department, {})
    return dept.get("common_procedures", {})


def list_departments() -> list:
    """Returns all departments in the rate card."""
    try:
        return list(_load().keys())
    except Exception:
        return []
