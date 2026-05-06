"""
Hospital/clinic search using Google Places API (New).

Two endpoints used:
  searchNearby  — for broad "all hospitals within radius" queries (no keyword)
  searchText    — for department-specific queries ("cardiologist hospital near me")
                  Works far better than passing textQuery to searchNearby (which errors).

Fallback chain: Places API → seed_hospitals.json → GIPSA city match
"""

import os, json, math, requests
from dotenv import load_dotenv
from functions.popular_times import get_wait_indicator
from functions.gipsa import search_gipsa, is_gipsa_empanelled

load_dotenv()

_SEED_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "seed_hospitals.json")
_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
_TEXT_URL   = "https://places.googleapis.com/v1/places:searchText"
_TIMEOUT    = 5

_FIELD_MASK = ",".join([
    "places.displayName",
    "places.id",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.rating",
    "places.userRatingCount",
    "places.currentOpeningHours",
    "places.regularOpeningHours",
    "places.businessStatus",
    "places.location",
    "places.types",
])


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return round(R * 2 * math.asin(math.sqrt(a)), 2)


def _key() -> str:
    return os.getenv("GOOGLE_PLACES_API_KEY", "")


def _place_to_dict(p: dict, user_lat: float, user_lng: float, place_type: str) -> dict:
    loc   = p.get("location", {})
    p_lat = loc.get("latitude")
    p_lng = loc.get("longitude")
    coh   = p.get("currentOpeningHours", {})
    roh   = p.get("regularOpeningHours", {})
    name  = p.get("displayName", {}).get("text", "Unknown")
    return {
        "name":          name,
        "type":          place_type,
        "address":       p.get("formattedAddress", ""),
        "phone":         p.get("nationalPhoneNumber", ""),
        "distance_km":   _haversine_km(user_lat, user_lng, p_lat, p_lng) if p_lat and p_lng else None,
        "rating":        p.get("rating"),
        "review_count":  p.get("userRatingCount"),
        "open_now":      coh.get("openNow"),
        "opening_hours": roh.get("weekdayDescriptions"),
        "place_id":      p.get("id", ""),
        "lat":           p_lat,
        "lng":           p_lng,
        "gipsa":         is_gipsa_empanelled(name),
        "wait_indicator": get_wait_indicator(),
    }


def _search_nearby(lat: float, lng: float, types: list, radius_m: int) -> list:
    """searchNearby — no keyword, pure type + location filter."""
    if not _key():
        return []
    try:
        r = requests.post(_NEARBY_URL,
            headers={"X-Goog-Api-Key": _key(), "X-Goog-FieldMask": _FIELD_MASK},
            json={
                "includedTypes":       types,
                "maxResultCount":      10,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius_m),
                    }
                },
                "rankPreference": "DISTANCE",
            },
            timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json().get("places", [])
    except Exception:
        return []


def _search_text(query: str, lat: float, lng: float, radius_m: int) -> list:
    """searchText — natural language query with location bias. Best for department searches."""
    if not _key():
        return []
    try:
        r = requests.post(_TEXT_URL,
            headers={"X-Goog-Api-Key": _key(), "X-Goog-FieldMask": _FIELD_MASK},
            json={
                "textQuery":      query,
                "maxResultCount": 10,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius_m),
                    }
                },
            },
            timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json().get("places", [])
    except Exception:
        return []


def _dedupe_and_convert(raw: list, lat: float, lng: float, max_results: int = 5) -> list:
    seen, results = set(), []
    for p in raw:
        name = p.get("displayName", {}).get("text", "")
        if name in seen:
            continue
        seen.add(name)
        types = p.get("types", [])
        ptype = "clinic" if any(t in types for t in ("clinic", "doctor", "health", "dentist")) else "hospital"
        results.append(_place_to_dict(p, lat, lng, ptype))
    results.sort(key=lambda x: x["distance_km"] or 99)
    return results[:max_results]


def _seed_fallback(department: str = None) -> list:
    try:
        with open(_SEED_PATH, encoding="utf-8") as f:
            hospitals = json.load(f)
        if department:
            hospitals = [h for h in hospitals if department in h.get("departments", [])]
        return hospitals or json.load(open(_SEED_PATH))
    except Exception:
        return []


def _seed_to_dict(h: dict, user_lat=None, user_lng=None) -> dict:
    dist = None
    if user_lat and user_lng and h.get("lat") and h.get("lng"):
        dist = _haversine_km(user_lat, user_lng, h["lat"], h["lng"])
    return {
        "name":          h.get("name", ""),
        "type":          h.get("type", "hospital"),
        "address":       h.get("address", ""),
        "phone":         h.get("phone", ""),
        "distance_km":   dist,
        "rating":        h.get("rating"),
        "review_count":  None,
        "open_now":      h.get("open_now"),
        "opening_hours": None,
        "place_id":      h.get("place_id"),
        "lat":           h.get("lat"),
        "lng":           h.get("lng"),
        "gipsa":         is_gipsa_empanelled(h.get("name", "")),
        "wait_indicator": get_wait_indicator(),
    }


# ─────────────────────────────────────────────────────────────

# Keywords that must NOT appear in result names for a given department.
# Catches blatant mismatches like an eye clinic for leg pain.
_DEPT_EXCLUSIONS = {
    "Cardiology":       ["eye", "dental", "dent", "skin", "derma", "ortho", "gynae", "gynec"],
    "Orthopedics":      ["eye", "dental", "dent", "skin", "derma", "cardiac", "heart", "gynae"],
    "Neurology":        ["eye", "dental", "dent", "skin", "derma", "orthop", "gynae"],
    "Gastroenterology": ["eye", "dental", "dent", "skin", "derma", "orthop", "cardiac"],
    "Dermatology":      ["eye", "dental", "dent", "cardiac", "heart", "orthop", "neuro"],
    "Ophthalmology":    ["dental", "dent", "orthop", "cardiac", "heart", "gastro"],
    "ENT":              ["eye", "ophthal", "dental", "cardiac", "orthop", "skin"],
    "Pulmonology":      ["eye", "dental", "dent", "skin", "derma", "orthop"],
    "Urology":          ["eye", "dental", "dent", "skin", "derma", "cardiac"],
    "Gynecology":       ["eye", "dental", "dent", "orthop", "cardiac", "neuro"],
    "Psychiatry":       ["eye", "dental", "dent", "orthop", "cardiac", "skin"],
    "Pediatrics":       ["eye", "dental", "dent", "skin", "cardiac"],
    "Dentistry":        ["eye", "ophthal", "cardiac", "orthop", "neuro", "gastro"],
    "Endocrinology":    ["eye", "dental", "dent", "orthop"],
}

def _is_relevant(place_name: str, department: str) -> bool:
    """Returns False if the place name contains a keyword that clearly
    contradicts the department being searched."""
    exclusions = _DEPT_EXCLUSIONS.get(department, [])
    name_lower = place_name.lower()
    return not any(excl in name_lower for excl in exclusions)


# Department → human-readable search phrases
_DEPT_QUERIES = {
    "Cardiology":        "cardiologist heart hospital",
    "Neurology":         "neurologist brain hospital",
    "Orthopedics":       "orthopedic bone joint hospital",
    "Gastroenterology":  "gastroenterologist stomach hospital",
    "Dermatology":       "dermatologist skin clinic",
    "ENT":               "ENT ear nose throat specialist",
    "Ophthalmology":     "eye hospital ophthalmologist",
    "Pulmonology":       "pulmonologist lung chest hospital",
    "Endocrinology":     "endocrinologist diabetes thyroid clinic",
    "Urology":           "urologist kidney hospital",
    "Gynecology":        "gynecologist women hospital",
    "Psychiatry":        "psychiatrist mental health clinic",
    "Pediatrics":        "pediatrician children hospital",
    "Dentistry":         "dentist dental clinic",
    "General Medicine":  "hospital clinic doctor",
    "Emergency":         "emergency hospital 24 hour",
}


def search_facilities(lat: float, lng: float, department: str,
                      radius_m: int = 5000) -> dict:
    """
    Department-specific hospital/clinic search.

    Strategy:
      1. searchText with a department-specific natural language query
         e.g. "orthopedic bone joint hospital near me" for Orthopedics
      2. Filter results: drop places whose name clearly contradicts the dept
         (e.g. "Mumbai Eye Hospital" for an Orthopedics search)
      3. If fewer than 3 relevant results, do a second broader text search
         e.g. "hospital near me" — but still filter for relevance
      4. Falls back to seed_hospitals.json if API unavailable

    Does NOT use searchNearby — that returns anything nearby (eye clinic
    for leg pain, dental clinic for chest pain, etc.)

    Returns:
    {
      "nearby": [...],   # up to 5, sorted by distance_km, all relevant
      "gipsa":  [...],   # GIPSA empanelled hospitals in the user's city
    }
    """
    dept_query = _DEPT_QUERIES.get(department, "hospital clinic doctor")

    # Primary: specific department query
    raw = _search_text(f"{dept_query} near me", lat, lng, radius_m)

    # Filter for relevance before converting
    relevant = [p for p in raw
                if _is_relevant(p.get("displayName", {}).get("text", ""), department)]

    # If we got fewer than 3 relevant results, add a broader hospital search
    # and filter that too — General Medicine accepts anything
    if len(relevant) < 3:
        broader = _search_text("hospital clinic near me", lat, lng, radius_m)
        seen_ids = {p.get("id") for p in relevant}
        for p in broader:
            if p.get("id") not in seen_ids:
                if _is_relevant(p.get("displayName", {}).get("text", ""), department):
                    relevant.append(p)
                    seen_ids.add(p.get("id"))

    nearby = _dedupe_and_convert(relevant, lat, lng, max_results=5)

    # Fallback to seed if API gave nothing
    if not nearby:
        seeds = _seed_fallback(department)
        nearby = sorted(
            [_seed_to_dict(h, lat, lng) for h in seeds],
            key=lambda x: x["distance_km"] or 99
        )[:5]

    # GIPSA: same relevance filter — don't show an eye clinic for leg pain
    # Two passes:
    #   1. Department-keyword search (e.g. "ortho" for Orthopedics)
    #   2. If fewer than 3 remain, fall back to all GIPSA in city
    #      but still drop obvious mismatches via _is_relevant
    dept_kw = _DEPT_QUERIES.get(department, "").split()[0]   # first word e.g. "orthopedic"
    gipsa_specific = search_gipsa(lat, lng, keyword=dept_kw, max_results=8)

    if len(gipsa_specific) < 3:
        # Add multi-specialty hospitals (no exclusion keyword in name)
        all_gipsa = search_gipsa(lat, lng, keyword=None, max_results=20)
        seen_names = {h["name"] for h in gipsa_specific}
        for h in all_gipsa:
            if h["name"] not in seen_names and _is_relevant(h["name"], department):
                gipsa_specific.append(h)
                seen_names.add(h["name"])
            if len(gipsa_specific) >= 8:
                break

    return {"nearby": nearby, "gipsa": gipsa_specific}


def get_emergency_hospitals(lat: float, lng: float) -> list:
    """Returns nearest hospitals for the emergency overlay."""
    text_places   = _search_text("emergency hospital 24 hour", lat, lng, 8000)
    nearby_places = _search_nearby(lat, lng, ["hospital"], 8000)
    combined = text_places + nearby_places
    results = _dedupe_and_convert(combined, lat, lng, max_results=5)
    if not results:
        seeds = _seed_fallback()
        results = sorted(
            [_seed_to_dict(h, lat, lng) for h in seeds],
            key=lambda x: x["distance_km"] or 99
        )[:5]
    return results
