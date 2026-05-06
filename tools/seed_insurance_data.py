"""
Seed insurance network data for demo.
Real hospital names, realistic city coverage based on publicly known insurer networks.
Run directly or imported by parse_insurance_pdf.py as fallback.

  python3 tools/seed_insurance_data.py
"""
import json, time
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "data" / "insurance_networks"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
#  Hospital master list — real names across major Indian cities
# ─────────────────────────────────────────────────────────────

# fmt: off
HOSPITALS = {
    # ── MUMBAI ──────────────────────────────────────────────
    "MUM_001": {"name": "Kokilaben Dhirubhai Ambani Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_002": {"name": "P. D. Hinduja Hospital and Medical Research Centre", "city": "Mumbai", "state": "MH"},
    "MUM_003": {"name": "Lilavati Hospital and Research Centre", "city": "Mumbai", "state": "MH"},
    "MUM_004": {"name": "Nanavati Super Speciality Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_005": {"name": "Breach Candy Hospital Trust", "city": "Mumbai", "state": "MH"},
    "MUM_006": {"name": "Asian Heart Institute", "city": "Mumbai", "state": "MH"},
    "MUM_007": {"name": "Fortis Hiranandani Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_008": {"name": "Seven Hills Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_009": {"name": "Holy Family Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_010": {"name": "Wockhardt Hospital Mumbai Central", "city": "Mumbai", "state": "MH"},
    "MUM_011": {"name": "Bombay Hospital and Medical Research Centre", "city": "Mumbai", "state": "MH"},
    "MUM_012": {"name": "Jaslok Hospital and Research Centre", "city": "Mumbai", "state": "MH"},
    "MUM_013": {"name": "Saifee Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_014": {"name": "Global Hospital Mumbai", "city": "Mumbai", "state": "MH"},
    "MUM_015": {"name": "Sir H. N. Reliance Foundation Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_016": {"name": "KEM Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_017": {"name": "Lokmanya Tilak Municipal General Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_018": {"name": "Tata Memorial Hospital", "city": "Mumbai", "state": "MH"},
    "MUM_019": {"name": "Jupiter Hospital Thane", "city": "Thane", "state": "MH"},
    "MUM_020": {"name": "Fortis Hospital Mulund", "city": "Mumbai", "state": "MH"},
    # ── DELHI / NCR ──────────────────────────────────────────
    "DEL_001": {"name": "Apollo Hospital Indraprastha", "city": "New Delhi", "state": "DL"},
    "DEL_002": {"name": "Fortis Memorial Research Institute", "city": "Gurugram", "state": "HR"},
    "DEL_003": {"name": "Max Super Speciality Hospital Saket", "city": "New Delhi", "state": "DL"},
    "DEL_004": {"name": "BLK-Max Super Speciality Hospital", "city": "New Delhi", "state": "DL"},
    "DEL_005": {"name": "Sir Ganga Ram Hospital", "city": "New Delhi", "state": "DL"},
    "DEL_006": {"name": "Medanta The Medicity", "city": "Gurugram", "state": "HR"},
    "DEL_007": {"name": "Artemis Hospital", "city": "Gurugram", "state": "HR"},
    "DEL_008": {"name": "AIIMS New Delhi", "city": "New Delhi", "state": "DL"},
    "DEL_009": {"name": "Safdarjung Hospital", "city": "New Delhi", "state": "DL"},
    "DEL_010": {"name": "Maulana Azad Medical College Hospital", "city": "New Delhi", "state": "DL"},
    "DEL_011": {"name": "Manipal Hospital Dwarka", "city": "New Delhi", "state": "DL"},
    "DEL_012": {"name": "Venkateshwar Hospital", "city": "New Delhi", "state": "DL"},
    "DEL_013": {"name": "Yashoda Hospital Ghaziabad", "city": "Ghaziabad", "state": "UP"},
    "DEL_014": {"name": "Kailash Hospital Noida", "city": "Noida", "state": "UP"},
    "DEL_015": {"name": "Narayan Superspeciality Hospital Gurugram", "city": "Gurugram", "state": "HR"},
    # ── BENGALURU ────────────────────────────────────────────
    "BLR_001": {"name": "Manipal Hospital Old Airport Road", "city": "Bengaluru", "state": "KA"},
    "BLR_002": {"name": "Fortis Hospital Bannerghatta Road", "city": "Bengaluru", "state": "KA"},
    "BLR_003": {"name": "Apollo Hospital Bannerghatta Road", "city": "Bengaluru", "state": "KA"},
    "BLR_004": {"name": "Narayana Health City", "city": "Bengaluru", "state": "KA"},
    "BLR_005": {"name": "Columbia Asia Hospital Whitefield", "city": "Bengaluru", "state": "KA"},
    "BLR_006": {"name": "Sakra World Hospital", "city": "Bengaluru", "state": "KA"},
    "BLR_007": {"name": "BGS Gleneagles Global Hospital", "city": "Bengaluru", "state": "KA"},
    "BLR_008": {"name": "Sparsh Hospital", "city": "Bengaluru", "state": "KA"},
    "BLR_009": {"name": "Victoria Hospital", "city": "Bengaluru", "state": "KA"},
    "BLR_010": {"name": "Bowring and Lady Curzon Hospital", "city": "Bengaluru", "state": "KA"},
    # ── PUNE ─────────────────────────────────────────────────
    "PUN_001": {"name": "Ruby Hall Clinic", "city": "Pune", "state": "MH"},
    "PUN_002": {"name": "Jehangir Hospital", "city": "Pune", "state": "MH"},
    "PUN_003": {"name": "Deenanath Mangeshkar Hospital", "city": "Pune", "state": "MH"},
    "PUN_004": {"name": "Sahyadri Super Speciality Hospital", "city": "Pune", "state": "MH"},
    "PUN_005": {"name": "KEM Hospital Pune", "city": "Pune", "state": "MH"},
    "PUN_006": {"name": "Aditya Birla Memorial Hospital", "city": "Pune", "state": "MH"},
    # ── KOLKATA ──────────────────────────────────────────────
    "KOL_001": {"name": "Apollo Gleneagles Hospital Kolkata", "city": "Kolkata", "state": "WB"},
    "KOL_002": {"name": "Fortis Hospital Anandapur", "city": "Kolkata", "state": "WB"},
    "KOL_003": {"name": "AMRI Hospitals Salt Lake", "city": "Kolkata", "state": "WB"},
    "KOL_004": {"name": "Peerless Hospital", "city": "Kolkata", "state": "WB"},
    "KOL_005": {"name": "SSKM Hospital", "city": "Kolkata", "state": "WB"},
    "KOL_006": {"name": "Belle Vue Clinic", "city": "Kolkata", "state": "WB"},
    # ── CHENNAI ──────────────────────────────────────────────
    "CHE_001": {"name": "Apollo Hospital Greams Road", "city": "Chennai", "state": "TN"},
    "CHE_002": {"name": "Fortis Malar Hospital", "city": "Chennai", "state": "TN"},
    "CHE_003": {"name": "MIOT International", "city": "Chennai", "state": "TN"},
    "CHE_004": {"name": "Kauvery Hospital", "city": "Chennai", "state": "TN"},
    "CHE_005": {"name": "Madras Medical College Hospital", "city": "Chennai", "state": "TN"},
}
# fmt: on

# ─────────────────────────────────────────────────────────────
#  Insurer networks — which hospital IDs are in-network
# ─────────────────────────────────────────────────────────────

NETWORKS = {
    "Star Health": {
        "slug": "star_health",
        "description": "Star Health and Allied Insurance — India's largest standalone health insurer",
        "coverage_note": "Cashless at all network hospitals. Pre-authorisation required for planned procedures.",
        "helpline": "1800-425-2255",
        # Star Health has a very broad network
        "hospital_ids": [
            "MUM_001","MUM_002","MUM_003","MUM_004","MUM_005","MUM_006",
            "MUM_007","MUM_008","MUM_009","MUM_010","MUM_011","MUM_012",
            "MUM_013","MUM_014","MUM_015","MUM_016","MUM_019","MUM_020",
            "DEL_001","DEL_002","DEL_003","DEL_004","DEL_005","DEL_006",
            "DEL_007","DEL_011","DEL_012","DEL_013","DEL_014","DEL_015",
            "BLR_001","BLR_002","BLR_003","BLR_004","BLR_005","BLR_006",
            "BLR_007","BLR_008",
            "PUN_001","PUN_002","PUN_003","PUN_004","PUN_006",
            "KOL_001","KOL_002","KOL_003","KOL_004","KOL_006",
            "CHE_001","CHE_002","CHE_003","CHE_004",
        ],
    },
    "HDFC ERGO": {
        "slug": "hdfc_ergo",
        "description": "HDFC ERGO Health Insurance — premium network focused on tertiary care",
        "coverage_note": "Cashless at network hospitals. Reimbursement available at non-network hospitals.",
        "helpline": "1800-2700-700",
        # HDFC ERGO has a smaller, premium network
        "hospital_ids": [
            "MUM_001","MUM_002","MUM_003","MUM_004","MUM_006",
            "MUM_007","MUM_012","MUM_015",
            "DEL_001","DEL_002","DEL_003","DEL_005","DEL_006","DEL_007",
            "DEL_011",
            "BLR_001","BLR_002","BLR_003","BLR_004","BLR_006",
            "PUN_001","PUN_002","PUN_004","PUN_006",
            "KOL_001","KOL_002","KOL_003",
            "CHE_001","CHE_002","CHE_003",
        ],
    },
    "Niva Bupa": {
        "slug": "niva_bupa",
        "description": "Niva Bupa Health Insurance (formerly Max Bupa) — ReAssure and Go Active plans",
        "coverage_note": "Direct claim settlement at network hospitals. No pre-authorisation for OPD.",
        "helpline": "1860-500-8888",
        "hospital_ids": [
            "MUM_001","MUM_002","MUM_003","MUM_004","MUM_006","MUM_009",
            "MUM_010","MUM_011","MUM_013","MUM_014","MUM_015",
            "DEL_001","DEL_003","DEL_004","DEL_005","DEL_006",
            "DEL_007","DEL_011","DEL_012",
            "BLR_001","BLR_002","BLR_003","BLR_004","BLR_005","BLR_006",
            "PUN_001","PUN_003","PUN_004",
            "KOL_001","KOL_003","KOL_004",
            "CHE_001","CHE_003","CHE_004",
        ],
    },
    "New India Assurance": {
        "slug": "new_india_assurance",
        "description": "New India Assurance — largest PSU general insurer. Mediclaim policy.",
        "coverage_note": "Broad network. Government hospitals always covered. Cashless at empanelled hospitals.",
        "helpline": "1800-209-1415",
        # PSU insurer — broader coverage including government hospitals
        "hospital_ids": [
            "MUM_001","MUM_002","MUM_003","MUM_004","MUM_005","MUM_006",
            "MUM_007","MUM_008","MUM_009","MUM_010","MUM_011","MUM_016",
            "MUM_017","MUM_018","MUM_019","MUM_020",
            "DEL_001","DEL_002","DEL_003","DEL_004","DEL_005","DEL_006",
            "DEL_007","DEL_008","DEL_009","DEL_010","DEL_011","DEL_012",
            "DEL_013","DEL_014","DEL_015",
            "BLR_001","BLR_002","BLR_003","BLR_004","BLR_005","BLR_006",
            "BLR_007","BLR_008","BLR_009","BLR_010",
            "PUN_001","PUN_002","PUN_003","PUN_004","PUN_005","PUN_006",
            "KOL_001","KOL_002","KOL_003","KOL_004","KOL_005","KOL_006",
            "CHE_001","CHE_002","CHE_003","CHE_004","CHE_005",
        ],
    },
    "CGHS": {
        "slug": "cghs",
        "description": "Central Government Health Scheme — for central government employees & pensioners",
        "coverage_note": "Referral required for specialist care. Empanelled hospitals offer cashless treatment.",
        "helpline": "1800-11-4155",
        # CGHS covers primarily government hospitals + empanelled private hospitals
        "hospital_ids": [
            "MUM_002","MUM_003","MUM_004","MUM_005","MUM_016","MUM_017","MUM_018",
            "DEL_001","DEL_003","DEL_004","DEL_005","DEL_008","DEL_009","DEL_010",
            "DEL_011","DEL_013","DEL_014",
            "BLR_001","BLR_002","BLR_003","BLR_009","BLR_010",
            "PUN_001","PUN_002","PUN_005",
            "KOL_001","KOL_002","KOL_005",
            "CHE_001","CHE_005",
        ],
    },
}


def write_seed_data(only: str = None):
    """Write JSON files for all insurers (or just one if only= is set)."""
    for insurer_name, net in NETWORKS.items():
        if only and insurer_name != only:
            continue

        hospitals = [
            {**HOSPITALS[hid]}
            for hid in net["hospital_ids"]
            if hid in HOSPITALS
        ]
        hospitals.sort(key=lambda h: (h["city"], h["name"]))

        payload = {
            "insurer":      insurer_name,
            "slug":         net["slug"],
            "description":  net["description"],
            "coverage_note":net["coverage_note"],
            "helpline":     net["helpline"],
            "total":        len(hospitals),
            "source":       "seed_insurance_data.py — realistic demo data",
            "parsed_at":    "2025-05-06",
            "hospitals":    hospitals,
        }

        out = OUT_DIR / f"{net['slug']}.json"
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"  ✓ {insurer_name:30} → {len(hospitals)} hospitals → {out.name}")


if __name__ == "__main__":
    print("Writing seed insurance network data...\n")
    write_seed_data()
    print("\nDone.")
