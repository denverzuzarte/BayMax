"""
GIPSA hospital database — 2,179 government-empanelled Indian hospitals.
Source: Loop AI dataset (../anthropicc/List of GIPSA Hospitals - Sheet1.csv)

The CSV has no lat/lng. Proximity is done by:
  1. Mapping user coordinates → nearest city via CITY_CENTERS lookup
  2. Returning all GIPSA hospitals in that city
  3. Sorting by text similarity to department keyword if provided

GIPSA = Government Insurance PSU Association empanelment.
Being in this list means the hospital accepts government insurance schemes.
"""

import os, math
import pandas as pd

_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "anthropicc", "List of GIPSA Hospitals - Sheet1.csv"
)

# City centres (lat, lng) — used to match user location to a city
CITY_CENTERS = {
    "mumbai":        (19.0760, 72.8777),
    "pune":          (18.5204, 73.8567),
    "bengaluru":     (12.9716, 77.5946),
    "bangalore":     (12.9716, 77.5946),
    "kolkata":       (22.5726, 88.3639),
    "new delhi":     (28.6139, 77.2090),
    "delhi":         (28.6139, 77.2090),
    "faridabad":     (28.4089, 77.3178),
    "gurugram":      (28.4595, 77.0266),
    "ghaziabad":     (28.6692, 77.4538),
    "noida":         (28.5355, 77.3910),
    "greater noida": (28.4744, 77.5040),
    "rohini":        (28.7041, 77.1025),
    "ballabgarh":    (28.3416, 77.3138),
    "bangalore rural":(13.0057, 77.5960),
}

# Normalise messy city spellings from the CSV to canonical names
_CITY_NORM = {
    "new delhi":      "new delhi",
    "delhi":          "new delhi",
    "new delhi ":     "new delhi",
    "delhi ":         "new delhi",
    "bengaluru":      "bengaluru",
    "bangalore":      "bengaluru",
    "bangalore rural":"bengaluru",
    "gurugram":       "gurugram",
    "gurgaon":        "gurugram",
    "faridabad":      "faridabad",
    "ghaziabad":      "ghaziabad",
    "noida":          "noida",
    "greater noida":  "noida",
    "rohini":         "new delhi",
    "ballabgarh":     "faridabad",
}

_df: pd.DataFrame | None = None


def _load() -> pd.DataFrame:
    global _df
    if _df is not None:
        return _df
    try:
        raw = pd.read_csv(_CSV)
        raw.columns = ["name", "address", "city"]
        raw = raw.dropna(subset=["name", "city"])
        raw["name"]      = raw["name"].str.strip()
        raw["address"]   = raw["address"].fillna("").str.strip()
        raw["city"]      = raw["city"].str.strip()
        raw["city_norm"] = raw["city"].str.lower().str.strip().map(
            lambda c: _CITY_NORM.get(c, c)
        )
        raw["name_lower"] = raw["name"].str.lower()
        _df = raw
    except Exception:
        _df = pd.DataFrame(columns=["name","address","city","city_norm","name_lower"])
    return _df


def _haversine(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    d = math.radians
    a = (math.sin(d(lat2-lat1)/2)**2
         + math.cos(d(lat1)) * math.cos(d(lat2))
         * math.sin(d(lng2-lng1)/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


def nearest_gipsa_city(lat: float, lng: float, max_km: float = 60) -> str | None:
    """Returns the GIPSA city name closest to the given coordinates, or None."""
    best, dist = None, float("inf")
    for city, (clat, clng) in CITY_CENTERS.items():
        d = _haversine(lat, lng, clat, clng)
        if d < dist:
            dist, best = d, city
    # Normalise to the canonical name used in the CSV
    if best and dist <= max_km:
        return _CITY_NORM.get(best, best)
    return None


def search_gipsa(lat: float, lng: float, keyword: str = None, max_results: int = 8) -> list:
    """
    Returns GIPSA hospitals near the user's coordinates.

    Algorithm:
      1. Find the closest city from CITY_CENTERS (within 60km)
      2. Filter the CSV to that city (all spelling variants)
      3. Optionally filter by keyword in hospital name
      4. Return up to max_results hospitals

    Each result dict:
      name, address, city, source="GIPSA", dist_to_city_center_km
    """
    if lat is None or lng is None:
        return []

    df      = _load()
    city    = nearest_gipsa_city(lat, lng)
    if not city:
        return []

    mask    = df["city_norm"] == city
    subset  = df[mask].copy()

    if keyword:
        kw     = keyword.lower()
        subset = subset[subset["name_lower"].str.contains(kw, na=False)]

    clat, clng         = CITY_CENTERS.get(city, CITY_CENTERS.get("mumbai"))
    dist_to_city_center = round(_haversine(lat, lng, clat, clng), 1)

    results = []
    for _, row in subset.head(max_results).iterrows():
        results.append({
            "name":                   row["name"],
            "address":                row["address"],
            "city":                   row["city"],
            "type":                   "hospital",
            "source":                 "GIPSA",
            "distance_km":            None,   # no per-hospital coords
            "dist_to_city_center_km": dist_to_city_center,
            "rating":                 None,
            "review_count":           None,
            "open_now":               None,
            "opening_hours":          None,
            "phone":                  "",
            "place_id":               None,
            "lat":                    None,
            "lng":                    None,
            "gipsa":                  True,
        })
    return results


def is_gipsa_empanelled(hospital_name: str, city: str = None) -> bool:
    """Returns True if hospital_name appears in the GIPSA database."""
    df        = _load()
    name_frag = hospital_name.lower().strip()[:12]
    mask      = df["name_lower"].str.startswith(name_frag)
    if city:
        city_norm = _CITY_NORM.get(city.lower().strip(), city.lower().strip())
        mask      = mask & (df["city_norm"] == city_norm)
    return bool(df[mask].shape[0])
