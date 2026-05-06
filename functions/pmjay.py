import os
import json

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pmjay_mock.json")
_db = None

def _load() -> dict:
    global _db
    if _db is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            _db = json.load(f)
    return _db

def _not_found() -> dict:
    try:
        return _load()["NOT_FOUND"]
    except Exception:
        return {
            "eligible": False, "pmjay_id": None, "scheme": None,
            "family_coverage_inr": None, "remaining_inr": None,
            "card_status": "NOT_FOUND", "beneficiary_name": None,
        }

# ─────────────────────────────────────────────────────────────

def check_pmjay_eligibility(phone: str = None, pmjay_id: str = None) -> dict:
    """
    Checks PMJAY/State Scheme eligibility for the logged-in user.

    Currently uses data/pmjay_mock.json for demo.
    To swap to the real NHA API, replace the lookup below with:

        response = requests.post(
            "https://api.pmjay.gov.in/v1/beneficiary",
            headers={"Authorization": f"Bearer {os.environ.get('PMJAY_API_KEY')}"},
            json={"phone": phone} if phone else {"pmjay_id": pmjay_id},
            timeout=3
        )
        if response.status_code == 200:
            return response.json()
        return _not_found()

    Everything else — format_for_ui(), asyncio call, UI rendering — stays the same.

    Returns dict with keys:
      eligible, pmjay_id, scheme, family_coverage_inr,
      remaining_inr, card_status, beneficiary_name
    """
    if phone is None and pmjay_id is None:
        return _not_found()

    try:
        db = _load()
    except Exception:
        return _not_found()

    # Phone lookup
    if phone is not None:
        result = db.get(str(phone).strip())
        if result and result.get("card_status") != "NOT_FOUND":
            return result
        return _not_found()

    # pmjay_id lookup (scan all entries)
    for entry in db.values():
        if isinstance(entry, dict) and entry.get("pmjay_id") == pmjay_id:
            return entry

    return _not_found()


def format_for_ui(pmjay_result: dict) -> dict:
    """
    Converts raw PMJAY result into UI-ready display fields.

    Returns:
    {
      "badge": str | None,          # green badge text, or None (hide entirely)
      "coverage_text": str | None,  # e.g. "₹5,00,000 coverage — ₹5,00,000 remaining"
      "warning": str | None,        # amber warning text, or None
    }

    Callers:
      if badge is not None → show green badge
      if warning is not None → show amber warning below badge
      if badge is None → don't mention PMJAY at all
    """
    status = pmjay_result.get("card_status", "NOT_FOUND")

    if status in ("NOT_FOUND", "NOT_ENROLLED") or not pmjay_result.get("eligible"):
        return {"badge": None, "coverage_text": None, "warning": None}

    scheme = pmjay_result.get("scheme", "PMJAY")
    remaining = pmjay_result.get("remaining_inr")
    family_coverage = pmjay_result.get("family_coverage_inr")

    def fmt_inr(n):
        if n is None:
            return "N/A"
        return f"₹{n:,.0f}".replace(",", ",")

    if status == "LIMIT_REACHED":
        return {
            "badge": f"{scheme} — Limit Reached",
            "coverage_text": f"{fmt_inr(family_coverage)} family coverage — limit used",
            "warning": "Annual coverage limit reached. Out-of-pocket charges may apply.",
        }

    # ACTIVE
    coverage_text = None
    if family_coverage is not None and remaining is not None:
        coverage_text = f"{fmt_inr(family_coverage)} coverage — {fmt_inr(remaining)} remaining"

    return {
        "badge": scheme,
        "coverage_text": coverage_text,
        "warning": None,
    }
