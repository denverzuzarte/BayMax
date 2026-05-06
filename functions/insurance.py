"""
Insurance network coverage lookup.
Reads pre-parsed JSON files from data/insurance_networks/.

Name matching uses a layered approach to handle variations:
  "Hinduja Hospital" ≈ "P. D. Hinduja Hospital and Medical Research Centre"
  "Kokilaben" ≈ "Kokilaben Dhirubhai Ambani Hospital"

Layer 1: exact lowercase match
Layer 2: first meaningful word match + city match
Layer 3: longest common subsequence ratio ≥ 0.65
"""

import os, re, json
from pathlib import Path
from functools import lru_cache

_NET_DIR = Path(__file__).parent.parent / "data" / "insurance_networks"

# Canonical insurer name → JSON slug mapping
INSURER_SLUGS = {
    "star health":        "star_health",
    "star health insurance": "star_health",
    "hdfc ergo":          "hdfc_ergo",
    "hdfc ergo health":   "hdfc_ergo",
    "niva bupa":          "niva_bupa",
    "max bupa":           "niva_bupa",
    "new india":          "new_india_assurance",
    "new india assurance":"new_india_assurance",
    "cghs":               "cghs",
    "central government health": "cghs",
}

# Words stripped before matching (noisy tokens)
_NOISE = {
    "hospital", "hospitals", "medical", "clinic", "centre", "center",
    "research", "institute", "healthcare", "health", "care", "and",
    "the", "a", "an", "of", "dr", "ltd", "pvt", "limited",
    "super", "speciality", "specialty", "multispeciality",
    "trust", "foundation", "society",
}


@lru_cache(maxsize=8)
def _load_network(slug: str) -> dict:
    path = _NET_DIR / f"{slug}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _resolve_slug(insurer_name: str) -> str | None:
    """Map user-entered insurer name to a JSON slug."""
    if not insurer_name:
        return None
    norm = insurer_name.lower().strip()
    if norm in INSURER_SLUGS:
        return INSURER_SLUGS[norm]
    # Partial match
    for key, slug in INSURER_SLUGS.items():
        if key in norm or norm in key:
            return slug
    return None

def _normalise_city(city: str) -> str:
    """Normalise common Indian city name variations."""
    c = city.lower().strip()
    aliases = {
        "bangalore": "bengaluru",
        "bombay":    "mumbai",
        "calcutta":  "kolkata",
        "madras":    "chennai",
        "pondicherry": "puducherry",
    }
    return aliases.get(c, c)
def _tokenize(name: str) -> set[str]:
    """Lowercase, strip punctuation, remove noise words."""
    tokens = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return {t for t in tokens if t not in _NOISE and len(t) > 2}


def _lcs_ratio(a: str, b: str) -> float:
    """Longest common subsequence ratio (fast approximation via token overlap)."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    overlap = ta & tb
    return len(overlap) / max(len(ta), len(tb))


def check_coverage(hospital_name: str, city: str = None, insurer_name: str = None) -> dict:
    """
    Returns coverage info for a hospital under a specific insurer.

    {
      "in_network":    bool,
      "insurer":       str,        # canonical insurer name
      "badge":         str | None, # e.g. "Star Health ✓"
      "coverage_note": str | None,
      "helpline":      str | None,
    }
    """
    slug = _resolve_slug(insurer_name or "")
    if not slug:
        return _no_coverage(insurer_name)

    net = _load_network(slug)
    if not net or "hospitals" not in net:
        return _no_coverage(insurer_name)

    hospitals   = net["hospitals"]
    name_lower  = hospital_name.lower().strip()
    city_lower  = _normalise_city(city or "")

    # ── Layer 1: exact name match ────────────────────────────
    for h in hospitals:
        h_name = h["name"].lower()
        h_city = h.get("city", "").lower()
        if name_lower == h_name:
            if not city_lower or city_lower in h_city or h_city in city_lower:
                return _hit(net)

    # ── Layer 2: first significant word match + city ─────────
    query_tokens = _tokenize(hospital_name)
    if query_tokens:
        for h in hospitals:
            h_city = h.get("city", "").lower()
            city_ok = (not city_lower
                       or city_lower in h_city
                       or h_city in city_lower)
            if not city_ok:
                continue
            h_tokens = _tokenize(h["name"])
            # All query tokens present in hospital tokens
            if query_tokens and query_tokens.issubset(h_tokens):
                return _hit(net)
            # Hospital tokens all present in query
            if h_tokens and h_tokens.issubset(query_tokens):
                return _hit(net)

    # ── Layer 3: fuzzy token overlap ─────────────────────────
    best_ratio = 0.0
    for h in hospitals:
        h_city = h.get("city", "").lower()
        city_ok = (not city_lower
                   or city_lower in h_city
                   or h_city in city_lower)
        if not city_ok:
            continue
        r = _lcs_ratio(hospital_name, h["name"])
        if r > best_ratio:
            best_ratio = r

    if best_ratio >= 0.65:
        return _hit(net)

    return _no_coverage(insurer_name, net)


def get_network_hospitals(insurer_name: str, city: str = None) -> list:
    """Returns all in-network hospitals for an insurer, optionally filtered by city."""
    slug = _resolve_slug(insurer_name or "")
    
    if not slug:
        return []
    net = _load_network(slug)
    hospitals = net.get("hospitals", [])
    if city:
        c = _normalise_city(city)
        hospitals = [h for h in hospitals
                     if c in h.get("city","").lower()
                     or h.get("city","").lower() in c]
    return hospitals


def get_insurer_info(insurer_name: str) -> dict:
    """Returns metadata about an insurer (helpline, coverage note, etc.)."""
    slug = _resolve_slug(insurer_name or "")
    if not slug:
        return {}
    net = _load_network(slug)
    return {
        "insurer":       net.get("insurer", insurer_name),
        "helpline":      net.get("helpline"),
        "coverage_note": net.get("coverage_note"),
        "total":         net.get("total", 0),
    }


def list_supported_insurers() -> list[str]:
    """Returns all insurer names with data files."""
    results = []
    for f in _NET_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            results.append(d.get("insurer", f.stem))
        except Exception:
            pass
    return sorted(results)


def _hit(net: dict) -> dict:
    return {
        "in_network":    True,
        "insurer":       net.get("insurer", ""),
        "badge":         net.get("insurer", ""),
        "coverage_note": net.get("coverage_note"),
        "helpline":      net.get("helpline"),
    }

def _no_coverage(insurer_name: str, net: dict = None) -> dict:
    return {
        "in_network":    False,
        "insurer":       insurer_name or "",
        "badge":         None,
        "coverage_note": net.get("coverage_note") if net else None,
        "helpline":      net.get("helpline") if net else None,
    }
