import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
#  SYMPTOM MAP  (English only)
#  Translation layer handles incoming non-English text upstream.
#  Format: "keyword": ("Department", "Doctor Type")
#
#  Conservative defaults: route to General Physician first.
#  Claude escalates based on severity, duration, red flags.
# ─────────────────────────────────────────────────────────────

SYMPTOM_MAP = {

    # ── CARDIOLOGY ──────────────────────────────────────────
    "chest pain":          ("Cardiology",  "Cardiologist"),
    "heart attack":        ("Emergency",   "Emergency Physician"),
    "palpitations":        ("Cardiology",  "Cardiologist"),
    "irregular heartbeat": ("Cardiology",  "Cardiologist"),
    "breathlessness":      ("Cardiology",  "Cardiologist"),
    "shortness of breath": ("Cardiology",  "Cardiologist"),
    "swollen legs":        ("Cardiology",  "Cardiologist"),
    "high blood pressure": ("Cardiology",  "Cardiologist"),
    "hypertension":        ("Cardiology",  "Cardiologist"),

    # ── NEUROLOGY ────────────────────────────────────────────
    # headache defaults to General Medicine — Claude escalates if
    # severe, recurring, or with vomiting / vision changes / stiff neck
    "headache":            ("General Medicine", "General Physician"),
    "migraine":            ("Neurology",   "Neurologist"),
    "seizure":             ("Neurology",   "Neurologist"),
    "fits":                ("Neurology",   "Neurologist"),
    "stroke":              ("Emergency",   "Emergency Physician"),
    "numbness":            ("Neurology",   "Neurologist"),
    "tingling":            ("Neurology",   "Neurologist"),
    "memory loss":         ("Neurology",   "Neurologist"),
    "confusion":           ("Neurology",   "Neurologist"),
    "dizziness":           ("General Medicine", "General Physician"),
    "fainting":            ("Neurology",   "Neurologist"),
    "paralysis":           ("Emergency",   "Emergency Physician"),
    "tremor":              ("Neurology",   "Neurologist"),
    "shaking hands":       ("Neurology",   "Neurologist"),

    # ── GASTROENTEROLOGY ─────────────────────────────────────
    "stomach pain":        ("Gastroenterology", "Gastroenterologist"),
    "abdominal pain":      ("Gastroenterology", "Gastroenterologist"),
    "stomach ache":        ("General Medicine", "General Physician"),
    "nausea":              ("General Medicine", "General Physician"),
    "vomiting":            ("General Medicine", "General Physician"),
    "diarrhea":            ("General Medicine", "General Physician"),
    "loose motions":       ("General Medicine", "General Physician"),
    "constipation":        ("General Medicine", "General Physician"),
    "acidity":             ("General Medicine", "General Physician"),
    "acid reflux":         ("Gastroenterology", "Gastroenterologist"),
    "heartburn":           ("General Medicine", "General Physician"),
    "bloating":            ("General Medicine", "General Physician"),
    "jaundice":            ("Gastroenterology", "Gastroenterologist"),
    "liver pain":          ("Gastroenterology", "Gastroenterologist"),
    "blood in stool":      ("Gastroenterology", "Gastroenterologist"),
    "black stool":         ("Gastroenterology", "Gastroenterologist"),

    # ── ORTHOPEDICS ──────────────────────────────────────────
    "joint pain":          ("Orthopedics",  "Orthopedic Surgeon"),
    "knee pain":           ("Orthopedics",  "Orthopedic Surgeon"),
    "back pain":           ("General Medicine", "General Physician"),
    "neck pain":           ("General Medicine", "General Physician"),
    "shoulder pain":       ("General Medicine", "General Physician"),
    "fracture":            ("Orthopedics",  "Orthopedic Surgeon"),
    "broken bone":         ("Orthopedics",  "Orthopedic Surgeon"),
    "sprain":              ("General Medicine", "General Physician"),
    "swollen joint":       ("Orthopedics",  "Orthopedic Surgeon"),
    "arthritis":           ("Orthopedics",  "Rheumatologist"),
    "slip disc":           ("Orthopedics",  "Orthopedic Surgeon"),
    "sports injury":       ("Orthopedics",  "Orthopedic Surgeon"),

    # ── DERMATOLOGY ──────────────────────────────────────────
    "skin rash":           ("Dermatology",  "Dermatologist"),
    "itching":             ("General Medicine", "General Physician"),
    "acne":                ("Dermatology",  "Dermatologist"),
    "pimples":             ("General Medicine", "General Physician"),
    "eczema":              ("Dermatology",  "Dermatologist"),
    "psoriasis":           ("Dermatology",  "Dermatologist"),
    "hair loss":           ("Dermatology",  "Dermatologist"),
    "fungal infection":    ("Dermatology",  "Dermatologist"),
    "ringworm":            ("Dermatology",  "Dermatologist"),
    "skin allergy":        ("Dermatology",  "Dermatologist"),
    "hives":               ("Dermatology",  "Dermatologist"),
    "urticaria":           ("Dermatology",  "Dermatologist"),

    # ── ENT ──────────────────────────────────────────────────
    "ear pain":            ("ENT",          "ENT Specialist"),
    "hearing loss":        ("ENT",          "ENT Specialist"),
    "ringing in ears":     ("ENT",          "ENT Specialist"),
    "tinnitus":            ("ENT",          "ENT Specialist"),
    "sore throat":         ("General Medicine", "General Physician"),
    "throat pain":         ("ENT",          "ENT Specialist"),
    "tonsils":             ("ENT",          "ENT Specialist"),
    "sinusitis":           ("ENT",          "ENT Specialist"),
    "blocked nose":        ("General Medicine", "General Physician"),
    "nosebleed":           ("ENT",          "ENT Specialist"),
    "snoring":             ("ENT",          "ENT Specialist"),

    # ── OPHTHALMOLOGY ────────────────────────────────────────
    "eye pain":            ("Ophthalmology","Ophthalmologist"),
    "blurred vision":      ("Ophthalmology","Ophthalmologist"),
    "vision loss":         ("Emergency",    "Emergency Physician"),
    "red eye":             ("Ophthalmology","Ophthalmologist"),
    "watery eyes":         ("General Medicine", "General Physician"),
    "eye infection":       ("Ophthalmology","Ophthalmologist"),
    "conjunctivitis":      ("Ophthalmology","Ophthalmologist"),
    "cataract":            ("Ophthalmology","Ophthalmologist"),
    "glaucoma":            ("Ophthalmology","Ophthalmologist"),

    # ── PULMONOLOGY ──────────────────────────────────────────
    "persistent cough":    ("Pulmonology",  "Pulmonologist"),
    "coughing blood":      ("Emergency",    "Emergency Physician"),
    "chest infection":     ("Pulmonology",  "Pulmonologist"),
    "wheezing":            ("Pulmonology",  "Pulmonologist"),
    "pneumonia":           ("Pulmonology",  "Pulmonologist"),
    "tuberculosis":        ("Pulmonology",  "Pulmonologist"),
    "asthma":              ("Pulmonology",  "Pulmonologist"),
    "cough":               ("General Medicine", "General Physician"),

    # ── ENDOCRINOLOGY ────────────────────────────────────────
    "hormonal imbalance":  ("Endocrinology","Endocrinologist"),
    "diabetes":            ("Endocrinology","Endocrinologist/Diabetologist"),
    "thyroid":             ("Endocrinology","Endocrinologist"),
    "weight gain":         ("General Medicine", "General Physician"),
    "weight loss":         ("General Medicine", "General Physician"),
    "fatigue":             ("General Medicine", "General Physician"),

    # ── UROLOGY ──────────────────────────────────────────────
    "urinary problem":     ("Urology",      "Urologist"),
    "burning urination":   ("Urology",      "Urologist"),
    "frequent urination":  ("General Medicine", "General Physician"),
    "blood in urine":      ("Urology",      "Urologist"),
    "kidney stone":        ("Urology",      "Urologist"),
    "kidney pain":         ("Urology",      "Urologist"),
    "prostate":            ("Urology",      "Urologist"),

    # ── GYNECOLOGY ───────────────────────────────────────────
    "irregular periods":   ("Gynecology",   "Gynecologist"),
    "vaginal discharge":   ("Gynecology",   "Gynecologist"),
    "breast pain":         ("Gynecology",   "Gynecologist"),
    "menstrual":           ("Gynecology",   "Gynecologist"),
    "menopause":           ("Gynecology",   "Gynecologist"),
    "pregnancy":           ("Gynecology",   "Gynecologist/Obstetrician"),
    "pcos":                ("Gynecology",   "Gynecologist"),

    # ── PSYCHIATRY ───────────────────────────────────────────
    "mental health":       ("Psychiatry",   "Psychiatrist"),
    "panic attack":        ("Psychiatry",   "Psychiatrist"),
    "hallucination":       ("Psychiatry",   "Psychiatrist"),
    "schizophrenia":       ("Psychiatry",   "Psychiatrist"),
    "depression":          ("Psychiatry",   "Psychiatrist"),
    "self harm":           ("Emergency",    "Emergency Physician"),
    "suicidal":            ("Emergency",    "Emergency Physician"),
    "insomnia":            ("Psychiatry",   "Psychiatrist"),
    "bipolar":             ("Psychiatry",   "Psychiatrist"),
    "anxiety":             ("Psychiatry",   "Psychiatrist"),
    "stress":              ("General Medicine", "General Physician"),

    # ── PEDIATRICS ───────────────────────────────────────────
    "child fever":         ("Pediatrics",   "Pediatrician"),
    "child vomiting":      ("Pediatrics",   "Pediatrician"),
    "child rash":          ("Pediatrics",   "Pediatrician"),
    "vaccination":         ("Pediatrics",   "Pediatrician"),
    "newborn":             ("Pediatrics",   "Pediatrician"),

    # ── DENTISTRY ────────────────────────────────────────────
    "broken tooth":        ("Dentistry",    "Dentist"),
    "bleeding gums":       ("Dentistry",    "Dentist"),
    "toothache":           ("Dentistry",    "Dentist"),
    "tooth pain":          ("Dentistry",    "Dentist"),
    "gum pain":            ("Dentistry",    "Dentist"),
    "cavity":              ("Dentistry",    "Dentist"),

    # ── GENERAL MEDICINE ─────────────────────────────────────
    "fever":               ("General Medicine", "General Physician"),
    "cold":                ("General Medicine", "General Physician"),
    "flu":                 ("General Medicine", "General Physician"),
    "body ache":           ("General Medicine", "General Physician"),
    "weakness":            ("General Medicine", "General Physician"),
    "allergy":             ("General Medicine", "General Physician"),
}

# ─────────────────────────────────────────────────────────────
#  quick_department_lookup
# ─────────────────────────────────────────────────────────────

def quick_department_lookup(text: str):
    """
    Scans English text for symptom keywords. ~0ms, no network.

    Returns:
      None                          — no keyword matched
      (department, doctor_type)     — exactly one unique result
      [(dept, doc), ...]            — multiple distinct results; pass all to Claude
    """
    text_lower = text.lower()
    matches = []
    seen = set()

    for keyword in sorted(SYMPTOM_MAP.keys(), key=len, reverse=True):
        if keyword in text_lower:
            result = SYMPTOM_MAP[keyword]
            if result not in seen:
                matches.append(result)
                seen.add(result)

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return matches


# ─────────────────────────────────────────────────────────────
#  needs_pain_scale
# ─────────────────────────────────────────────────────────────

_PAIN_WORDS = ("pain", "ache")

def needs_pain_scale(text: str) -> bool:
    """
    Returns True if the current message contains 'pain' or 'ache'.

    Real-time check on the current message only — no history.
    The state machine in app.py tracks whether the pain scale
    question has already been asked this session and decides
    whether to fire it again. This function just detects the signal.

    When True, caller asks: "On a scale of 1 to 10, how much pain are you in?"
    and does NOT call Claude until the answer is received.
    """
    return any(w in text.lower() for w in _PAIN_WORDS)


# ─────────────────────────────────────────────────────────────
#  route_with_claude
# ─────────────────────────────────────────────────────────────

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "symptom_router.txt")

def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

def _format_history(symptom_history) -> str:
    if isinstance(symptom_history, str):
        return symptom_history
    lines = []
    for turn in symptom_history:
        role = "Patient" if turn.get("role") == "user" else "BayMax"
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines) if lines else "(no conversation yet)"

def _format_lookup(lookup_result) -> str:
    if lookup_result is None:
        return "(none)"
    if isinstance(lookup_result, tuple):
        dept, doc = lookup_result
        return f"Department: {dept}, Doctor type: {doc}"
    lines = [f"  - Department: {d}, Doctor type: {doc}" for d, doc in lookup_result]
    return "Multiple possible matches:\n" + "\n".join(lines)

_FALLBACK = {
    "is_medical": True,
    "urgency": "ROUTINE",
    "department": "General Medicine",
    "doctor_type": "General Physician",
    "likely_conditions": [],
    "routing_complete": False,
    "next_clarifying_question": "Can you tell me more about what you're experiencing?",
    "voice_response": "I'm having a little trouble right now. Could you tell me more about your symptoms so I can help you find the right doctor?",
    "reasoning": "API error — fallback to General Medicine",
}

def route_with_claude(
    symptom_history,
    user_profile: dict,
    available_departments: list = None,
) -> dict:
    """
    Calls Claude with the master prompt. All text must be in English by this point.
    Translation layer (functions/translate.py) handles conversion before this call.

    user_profile keys (all optional):
      name, age, city, insurance_provider, insurance_plan,
      pmjay_eligible, medical_history

    Returns structured routing dict or _FALLBACK on any error.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {**_FALLBACK, "reasoning": "No ANTHROPIC_API_KEY set — returning fallback"}

    p = user_profile
    all_text = (
        " ".join(t.get("content", "") for t in symptom_history)
        if isinstance(symptom_history, list)
        else str(symptom_history)
    )
    lookup = quick_department_lookup(all_text)

    dept_list = (
        "\n".join(f"  - {d}" for d in available_departments)
        if available_departments
        else "  (not provided — use your judgment)"
    )

    prompt = (
        _load_prompt()
        .replace("__NAME__",                str(p.get("name", "Unknown")))
        .replace("__AGE__",                 str(p.get("age", "Unknown")))
        .replace("__CITY__",                str(p.get("city", "Unknown")))
        .replace("__INSURANCE_PROVIDER__",  str(p.get("insurance_provider", "None")))
        .replace("__INSURANCE_PLAN__",      str(p.get("insurance_plan", "None")))
        .replace("__PMJAY_ELIGIBLE__",      str(p.get("pmjay_eligible", False)))
        .replace("__MEDICAL_HISTORY__",     str(p.get("medical_history", "None provided")))
        .replace("__SYMPTOM_HISTORY__",     _format_history(symptom_history))
        .replace("__QUICK_LOOKUP_RESULT__", _format_lookup(lookup))
        .replace("__AVAILABLE_DEPARTMENTS__", dept_list)
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        for key, default in _FALLBACK.items():
            result.setdefault(key, default)
        return result

    except json.JSONDecodeError as e:
        return {**_FALLBACK, "reasoning": f"JSON parse error: {e}"}
    except Exception as e:
        return {**_FALLBACK, "reasoning": f"API error: {e}"}
