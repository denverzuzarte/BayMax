import os
import json
import math
import requests
from dotenv import load_dotenv
from functions.popular_times import get_wait_indicator
from functions.gipsa import search_gipsa, is_gipsa_empanelled

load_dotenv()

_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_hospitals.json")
_API_URL   = "https://places.googleapis.com/v1/places:searchNearby"
_TIMEOUT   = 3

# Fields to request from Places API (New)
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


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return round(R * 2 * math.asin(math.sqrt(a)), 2)


def _place_to_dict(p: dict, user_lat: float, user_lng: float, place_type: str) -> dict:
    loc   = p.get("location", {})
    p_lat = loc.get("latitude")
    p_lng = loc.get("longitude")

    coh  = p.get("currentOpeningHours", {})
    roh  = p.get("regularOpeningHours", {})
    name = p.get("displayName", {}).get("text", "Unknown")

    # Check GIPSA empanelment from name alone (no city needed here)
    gipsa = is_gipsa_empanelled(name)

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
        "gipsa":         gipsa,
        "wait_indicator": get_wait_indicator(),
    }


def _api_search(lat: float, lng: float, included_types: list, radius_m: int, keyword: str = None) -> list:
    key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not key:
        return []

    body = {
        "includedTypes": included_types,
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
        "rankPreference": "DISTANCE",
    }
    if keyword:
        body["textQuery"] = keyword

    try:
        r = requests.post(
            _API_URL,
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": _FIELD_MASK},
            json=body,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("places", [])
    except Exception:
        return []


def _seed_fallback(department: str = None) -> list:
    try:
        with open(_SEED_PATH, "r", encoding="utf-8") as f:
            hospitals = json.load(f)
        if department:
            hospitals = [h for h in hospitals if department in h.get("departments", [])]
        return hospitals
    except Exception:
        return []


def _seed_to_dict(h: dict, user_lat: float = None, user_lng: float = None) -> dict:
    distance = None
    if user_lat and user_lng and h.get("lat") and h.get("lng"):
        distance = _haversine_km(user_lat, user_lng, h["lat"], h["lng"])
    return {
        "name":          h.get("name", ""),
        "type":          h.get("type", "hospital"),
        "address":       h.get("address", ""),
        "phone":         h.get("phone", ""),
        "distance_km":   distance,
        "rating":        h.get("rating"),
        "review_count":  None,
        "open_now":      h.get("open_now"),
        "opening_hours": None,
        "place_id":      h.get("place_id"),
        "lat":           h.get("lat"),
        "lng":           h.get("lng"),
        "wait_indicator": get_wait_indicator(),
    }


# ─────────────────────────────────────────────────────────────

def search_facilities(lat: float, lng: float, department: str, radius_m: int = 5000) -> dict:
    """
    Hybrid hospital search combining two sources:

    1. NEARBY  — Google Places API (New): real GPS proximity, ratings, phone,
                 open/closed status. Up to 5 results sorted by distance.
                 Falls back to seed_hospitals.json if API unavailable.

    2. GIPSA   — 2,179 government-empanelled hospitals from the Loop AI
                 dataset, matched by city proximity (within 60 km).
                 No lat/lng per hospital — shown as a separate "network" list.
                 Relevant for patients using government insurance schemes.

    Returns:
    {
      "nearby":  [...],   # up to 5, sorted by distance_km — use for map pins
      "gipsa":   [...],   # up to 8, city-level — use for insurance panel
    }
    """
    # ── Google Places ────────────────────────────────────────
    raw_places = _api_search(lat, lng, ["hospital"], radius_m, keyword=department)
    raw_places += _api_search(lat, lng, ["clinic", "doctor", "health"],
                               radius_m // 2, keyword=department)

    nearby = []
    if raw_places:
        seen = set()
        for p in raw_places:
            name = p.get("displayName", {}).get("text", "")
            if name in seen:
                continue
            seen.add(name)
            types = p.get("types", [])
            ptype = "clinic" if any(t in types for t in ("clinic","doctor","health")) else "hospital"
            nearby.append(_place_to_dict(p, lat, lng, ptype))
        nearby.sort(key=lambda x: x["distance_km"] or 99)
        nearby = nearby[:5]
    else:
        # Seed fallback — at least show something
        seeds = _seed_fallback(department) or _seed_fallback()
        results = [_seed_to_dict(h, lat, lng) for h in seeds]
        results.sort(key=lambda x: x["distance_km"] or 99)
        nearby = results[:5]

    # ── GIPSA ────────────────────────────────────────────────
    gipsa = search_gipsa(lat, lng, keyword=None, max_results=8)

    return {"nearby": nearby, "gipsa": gipsa}


def get_emergency_hospitals(lat: float, lng: float) -> list:
    """
    Returns up to 5 nearest hospitals (any type) for the emergency overlay.
    Always returns a plain list (not the nearby/gipsa dict).
    Falls back to seed_hospitals.json.
    """
    places = _api_search(lat, lng, ["hospital"], radius_m=8000, keyword="emergency")

    if places:
        results = [_place_to_dict(p, lat, lng, "hospital") for p in places]
        results.sort(key=lambda x: x["distance_km"] or 99)
        return results[:5]

    seeds = _seed_fallback()
    results = [_seed_to_dict(h, lat, lng) for h in seeds]
    results.sort(key=lambda x: x["distance_km"] or 99)
    return results[:5]
