import json
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

EMERGENCY_KEYWORDS = [
    # English
    "chest pain", "heart attack", "can't breathe", "cannot breathe",
    "not breathing", "stroke", "unconscious", "fainted", "fainting",
    "severe bleeding", "bleeding heavily", "poisoning", "overdose",
    "choking", "seizure", "convulsion", "dying", "not waking",
    "unconscious", "severe chest", "crushing chest",
    # Hindi
    "सीने में दर्द", "दिल का दौरा", "सांस नहीं", "बेहोश", "इमरजेंसी",
    "खून बह रहा", "दम घुट",
    # Marathi
    "छातीत दुखणे", "श्वास घेता येत नाही", "बेशुद्ध", "रक्त येत आहे",
    # Gujarati
    "છાતીમાં દુખાવો", "શ્વાસ નથી", "બેભાન",
    # Punjabi
    "ਛਾਤੀ ਵਿੱਚ ਦਰਦ", "ਸਾਹ ਨਹੀਂ", "ਬੇਹੋਸ਼",
]

EMERGENCY_RESPONSES = {
    "en": "This sounds serious. Please call 112 immediately.",
    "hi": "यह गंभीर लग रहा है। कृपया तुरंत 112 पर कॉल करें।",
    "mr": "हे गंभीर वाटते. कृपया ताबडतोब 112 वर कॉल करा.",
    "gu": "આ ગંભીર લાગે છે. કૃપા કરી તરત 112 પર ફોન કરો.",
    "pa": "ਇਹ ਗੰਭੀਰ ਲੱਗਦਾ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਤੁਰੰਤ 112 ਤੇ ਕਾਲ ਕਰੋ।",
}


def is_emergency(text: str) -> bool:
    """
    Keyword check across English, Hindi, Marathi, Gujarati, Punjabi.
    Short-circuits before any API or LLM call.
    """
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in EMERGENCY_KEYWORDS)


def get_emergency_response(lang: str = "en") -> str:
    """Returns the hardcoded emergency voice line for a given language."""
    return EMERGENCY_RESPONSES.get(lang, EMERGENCY_RESPONSES["en"])


def get_emergency_panel() -> list:
    """
    Reads data/emergency_numbers.json. Always works, no network.
    Returns list of {name, number, notes}.
    """
    path = os.path.join(_DATA_DIR, "emergency_numbers.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Absolute fallback — never fail silently in an emergency context
        return [
            {"name": "National Emergency", "number": "112", "notes": "Police, Fire, Ambulance"},
            {"name": "Ambulance",           "number": "108", "notes": "Free government ambulance"},
        ]
