"""
BayMax — Flask backend
All text processing happens in English; translate.py handles in/out conversion.

Endpoints:
  GET  /                  — serve static/index.html
  GET  /api/health        — health check
  POST /api/profile       — save user profile to session
  POST /api/chat          — main chat (text in, text + data out)
  POST /api/voice         — voice pipeline (audio in, audio + data out)
  POST /api/tts           — text → MP3 audio (for greeting playback)
  GET  /api/emergency     — emergency panel + optional nearest hospitals
  POST /api/search        — direct hospital search
"""

import os, uuid, tempfile, asyncio
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

import edge_tts
import speech_recognition as sr
from pydub import AudioSegment

from functions.emergency  import is_emergency, get_emergency_response, get_emergency_panel
from functions.symptom    import needs_pain_scale, route_with_claude
from functions.translate  import detect_language, translate_to_english, translate_to_language
from functions.places     import search_facilities, get_emergency_hospitals
from functions.pmjay      import check_pmjay_eligibility, format_for_ui
from functions.cghs       import get_cost_estimate
from functions.insurance          import check_coverage, get_insurer_info
from functions.treatment_validator import validate_treatment, preload_chunks

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# ─────────────────────────────────────────────────────────────
#  BayMax voice config
# ─────────────────────────────────────────────────────────────
BAYMAX_VOICE = "en-US-GuyNeural"
BAYMAX_RATE  = "-20%"
BAYMAX_PITCH = "-10Hz"

LANG_STT = {
    "English": "en-IN",
    "Hindi":   "hi-IN",
    "Marathi": "mr-IN",
    "Gujarati":"gu-IN",
    "Punjabi": "pa-IN",
}

GREETING = (
    "Hi, I am Baymax, your personal healthcare companion. "
    "I am not a doctor. I will help you find the right one. "
    "What's bothering you today?"
)
PAIN_SCALE_QUESTION = "On a scale of 1 to 10, how much pain are you in?"

# ─────────────────────────────────────────────────────────────
#  TTS helper
# ─────────────────────────────────────────────────────────────

async def _tts_async(text: str) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        path = tmp.name
    communicate = edge_tts.Communicate(text, BAYMAX_VOICE,
                                       rate=BAYMAX_RATE, pitch=BAYMAX_PITCH)
    await communicate.save(path)
    with open(path, "rb") as f:
        data = f.read()
    os.unlink(path)
    return data

def tts(text: str) -> bytes:
    """Synchronous wrapper for TTS. Returns MP3 bytes."""
    try:
        return asyncio.run(_tts_async(text))
    except Exception:
        return b""

# ─────────────────────────────────────────────────────────────
#  Session store  (in-memory; resets on server restart)
# ─────────────────────────────────────────────────────────────
sessions: dict = {}

def _new_session(user: dict = None) -> dict:
    return {
        "user":                user or {},
        "history":             [],
        "state":               "GREETING",
        "language":            "English",
        "clarification_count": 0,
        "pain_scale_asked":    False,
        "last_routing":        None,
        "last_facilities":     [],
    }

def _get_session(session_id: str) -> dict:
    if session_id not in sessions:
        sessions[session_id] = _new_session()
    return sessions[session_id]

# ─────────────────────────────────────────────────────────────
#  Parallel context fetch
# ─────────────────────────────────────────────────────────────

def _get_full_context(department: str, lat, lng, phone,
                      insurer: str = None) -> tuple:
    """
    Returns (facilities_dict, pmjay_ui, costs).
    facilities_dict = {"nearby": [...], "gipsa": [...]}
    Nearby results are annotated with insurance_badge if insurer is provided.
    """
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_fac   = ex.submit(search_facilities, lat, lng, department) if lat and lng else None
        f_pmjay = ex.submit(check_pmjay_eligibility, phone=phone)
        f_costs = ex.submit(get_cost_estimate, department)

        try:    fac_result = f_fac.result(timeout=6) if f_fac else {"nearby": [], "gipsa": []}
        except: fac_result = {"nearby": [], "gipsa": []}

        if isinstance(fac_result, list):
            fac_result = {"nearby": fac_result, "gipsa": []}

        try:    pmjay_raw = f_pmjay.result(timeout=4)
        except: pmjay_raw = {"eligible": False, "card_status": "NOT_FOUND",
                              "pmjay_id": None, "scheme": None,
                              "family_coverage_inr": None, "remaining_inr": None,
                              "beneficiary_name": None}

        try:    costs = f_costs.result(timeout=2)
        except: costs = None

    # Annotate nearby results with private insurance badge (pure dict lookup, ~0ms)
    if insurer:
        for facility in fac_result.get("nearby", []):
            cov = check_coverage(facility.get("name",""), facility.get("city",""), insurer)
            facility["insurance_badge"]    = cov["badge"]
            facility["insurance_helpline"] = cov.get("helpline")

    return fac_result, format_for_ui(pmjay_raw), costs

# ─────────────────────────────────────────────────────────────
#  State machine
# ─────────────────────────────────────────────────────────────

def _process_message(session_id: str, raw_message: str,
                     lang_override: str = None) -> dict:
    sess    = _get_session(session_id)
    user    = sess["user"]
    history = sess["history"]

    if lang_override:
        sess["language"] = lang_override

    # GREETING — transition to CLARIFICATION and fall through
    # so the user's first real message is processed in the same turn.
    # The greeting is prepended to whatever response is generated.
    is_first = (sess["state"] == "GREETING")
    if is_first:
        sess["state"] = "CLARIFICATION"
        if not lang_override:
            sess["language"] = detect_language(raw_message)

    lang = sess["language"]

    # Translate to English ───────────────────────────────────
    english = translate_to_english(raw_message) if lang != "English" else raw_message

    # Emergency check ────────────────────────────────────────
    if is_emergency(english):
        voice = get_emergency_response("en")
        if lang != "English":
            voice = translate_to_language(voice, lang)
        lat, lng_ = user.get("lat"), user.get("lng")
        nearest   = get_emergency_hospitals(lat, lng_) if lat and lng_ else []
        history.append({"role": "user",      "content": raw_message})
        history.append({"role": "assistant",  "content": voice})
        sess["state"] = "EMERGENCY"
        return _wrap(voice, "EMERGENCY", sess, is_first=is_first,
                     emergency=True,
                     emergency_panel=get_emergency_panel(),
                     facilities=nearest)

    # Pain scale auto-ask ────────────────────────────────────
    if needs_pain_scale(english) and not sess["pain_scale_asked"]:
        q = PAIN_SCALE_QUESTION
        if lang != "English":
            q = translate_to_language(q, lang)
        history.append({"role": "user",      "content": raw_message})
        history.append({"role": "assistant",  "content": q})
        sess["pain_scale_asked"] = True
        return _wrap(q, "CLARIFICATION", sess, is_first=is_first)

    # Build English history for Claude ───────────────────────
    eng_history = []
    for turn in history:
        content = (translate_to_english(turn["content"])
                   if lang != "English" and turn["role"] == "user"
                   else turn["content"])
        eng_history.append({"role": turn["role"], "content": content})
    eng_history.append({"role": "user", "content": english})

    # Route with Claude ──────────────────────────────────────
    routing = route_with_claude(
        symptom_history=eng_history,
        user_profile={
            "name":               user.get("name", "Unknown"),
            "age":                user.get("age", "Unknown"),
            "city":               user.get("city", "Unknown"),
            "insurance_provider": user.get("insurance_provider", "None"),
            "insurance_plan":     user.get("insurance_plan", "None"),
            "pmjay_eligible":     bool(user.get("pmjay_id")),
            "medical_history":    user.get("medical_history", "None provided"),
        },
    )

    # Non-medical ────────────────────────────────────────────
    if not routing.get("is_medical", True):
        voice = routing.get("voice_response", "I can only help with health questions.")
        if lang != "English":
            voice = translate_to_language(voice, lang)
        history.append({"role": "user",     "content": raw_message})
        history.append({"role": "assistant", "content": voice})
        return _wrap(voice, sess["state"], sess, is_first=is_first)

    # EMERGENCY from Claude ───────────────────────────────────
    if routing.get("urgency") == "EMERGENCY":
        voice = routing.get("voice_response", get_emergency_response("en"))
        if lang != "English":
            voice = translate_to_language(voice, lang)
        lat, lng_ = user.get("lat"), user.get("lng")
        nearest   = get_emergency_hospitals(lat, lng_) if lat and lng_ else []
        history.append({"role": "user",     "content": raw_message})
        history.append({"role": "assistant", "content": voice})
        sess["state"] = "EMERGENCY"
        return _wrap(voice, "EMERGENCY", sess, is_first=is_first,
                     routing=routing, emergency=True,
                     emergency_panel=get_emergency_panel(),
                     facilities=nearest)

    # Needs more clarification ───────────────────────────────
    if not routing.get("routing_complete") and sess["clarification_count"] < 3:
        q = routing.get("next_clarifying_question") or routing.get("voice_response", "")
        if lang != "English":
            q = translate_to_language(q, lang)
        history.append({"role": "user",     "content": raw_message})
        history.append({"role": "assistant", "content": q})
        sess["clarification_count"] += 1
        return _wrap(q, "CLARIFICATION", sess, is_first=is_first)

    # Routing complete → fire parallel context fetch ─────────
    department = routing.get("department", "General Medicine")
    lat, lng_  = user.get("lat"), user.get("lng")
    phone      = user.get("phone")
    insurer    = user.get("insurance_provider") or None

    facilities, pmjay_ui, costs = _get_full_context(
        department, lat, lng_, phone, insurer=insurer
    )
    sess["last_routing"]    = routing
    sess["last_facilities"] = facilities
    sess["state"]           = "RESULTS"

    voice = routing.get("voice_response", "")
    if lang != "English":
        voice = translate_to_language(voice, lang)

    history.append({"role": "user",     "content": raw_message})
    history.append({"role": "assistant", "content": voice})

    return _wrap(voice, "RESULTS", sess, is_first=is_first,
                 routing=routing, facilities=facilities,
                 pmjay=pmjay_ui, costs=costs)


def _wrap(response: str, state: str, sess: dict,
          is_first: bool = False, **extras) -> dict:
    if is_first and not response.startswith(GREETING[:20]):
        response = GREETING + " " + response
    fac = extras.get("facilities", {"nearby": [], "gipsa": []})
    if isinstance(fac, list):
        fac = {"nearby": fac, "gipsa": []}
    return {
        "response":        response,
        "state":           state,
        "routing":         extras.get("routing"),
        "facilities":      fac,
        "pmjay":           extras.get("pmjay"),
        "costs":           extras.get("costs"),
        "emergency":       extras.get("emergency", False),
        "emergency_panel": extras.get("emergency_panel"),
        "language":        sess.get("language", "English"),
    }

# ─────────────────────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/health")
def health():
    return jsonify({
        "status":   "ok",
        "sessions": len(sessions),
        "env": {
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "places":    bool(os.getenv("GOOGLE_PLACES_API_KEY")),
        }
    })

@app.route("/api/profile", methods=["POST"])
def set_profile():
    data       = request.get_json() or {}
    session_id = data.get("session_id") or str(uuid.uuid4())
    sess = _get_session(session_id)
    for k in ("name","age","city","lat","lng","phone",
              "insurance_provider","insurance_plan",
              "pmjay_id","abha_id","medical_history"):
        if data.get(k) is not None:
            sess["user"][k] = data[k]
    return jsonify({"session_id": session_id, "ok": True})

@app.route("/api/reset", methods=["POST"])
def reset_session():
    """Clear conversation history but keep the user profile."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    if session_id and session_id in sessions:
        user = sessions[session_id]["user"].copy()
        sessions[session_id] = _new_session(user)
    return jsonify({"ok": True})

@app.route("/api/chat", methods=["POST"])
def chat():
    data       = request.get_json() or {}
    message    = (data.get("message") or "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    language   = data.get("language")

    if not message:
        return jsonify({"error": "message is required"}), 400

    if "user" in data and isinstance(data["user"], dict):
        _get_session(session_id)["user"].update(data["user"])

    result = _process_message(session_id, message, lang_override=language)
    result["session_id"] = session_id
    return jsonify(result)

@app.route("/api/voice", methods=["POST"])
def voice():
    session_id = request.form.get("session_id") or str(uuid.uuid4())
    language   = request.form.get("language", "")

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    webm_path  = wav_path = None

    try:
        # Save WebM
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            audio_file.save(tmp.name)
            webm_path = tmp.name

        if os.path.getsize(webm_path) < 100:
            return jsonify({"error": "Audio too short — please speak for at least 1 second"}), 400

        # WebM → WAV
        seg = AudioSegment.from_file(webm_path, format="webm")
        wav_path = webm_path.replace(".webm", ".wav")
        seg.export(wav_path, format="wav")

        # STT
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio_data = recognizer.record(source)

        lang_obj  = _get_session(session_id).get("language", "English")
        stt_code  = LANG_STT.get(language or lang_obj, "en-IN")

        for attempt in range(3):
            try:
                transcript = recognizer.recognize_google(audio_data, language=stt_code)
                break
            except sr.UnknownValueError:
                return jsonify({"error": "Could not understand audio — please speak clearly"}), 400
            except sr.RequestError:
                if attempt == 2:
                    return jsonify({"error": "Speech recognition service unavailable"}), 503

    except Exception as e:
        return jsonify({"error": f"Audio processing failed: {str(e)}"}), 400
    finally:
        for p in [webm_path, wav_path]:
            if p and os.path.exists(p):
                try: os.unlink(p)
                except: pass

    result = _process_message(session_id, transcript,
                               lang_override=language or None)
    result["session_id"] = session_id
    result["transcript"] = transcript

    # TTS
    audio_bytes = tts(result["response"])
    result["audio"] = audio_bytes.hex() if audio_bytes else None

    return jsonify(result)

@app.route("/api/tts", methods=["POST"])
def tts_endpoint():
    text = (request.get_json() or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    audio_bytes = tts(text)
    if not audio_bytes:
        return jsonify({"error": "TTS failed"}), 500
    return jsonify({"audio": audio_bytes.hex()})

@app.route("/api/emergency")
def emergency():
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    return jsonify({
        "panel":   get_emergency_panel(),
        "nearest": get_emergency_hospitals(lat, lng) if lat and lng else [],
    })

@app.route("/api/search", methods=["POST"])
def search():
    data       = request.get_json() or {}
    department = data.get("department", "General Medicine")
    lat        = data.get("lat")
    lng        = data.get("lng")
    insurer    = data.get("insurer") or None
    session_id = data.get("session_id")

    if not lat or not lng:
        return jsonify({"error": "lat and lng are required"}), 400

    # Also accept insurer from session if not passed directly
    if not insurer and session_id and session_id in sessions:
        insurer = sessions[session_id]["user"].get("insurance_provider")

    fac = search_facilities(lat, lng, department, data.get("radius_m", 5000))
    if isinstance(fac, list):
        fac = {"nearby": fac, "gipsa": []}

    if insurer:
        for facility in fac.get("nearby", []):
            cov = check_coverage(facility.get("name",""), facility.get("city",""), insurer)
            facility["insurance_badge"]    = cov["badge"]
            facility["insurance_helpline"] = cov.get("helpline")

    return jsonify({
        "facilities":    fac,
        "costs":         get_cost_estimate(department),
        "insurer_info":  get_insurer_info(insurer) if insurer else None,
    })

@app.route("/api/validate-treatment", methods=["POST"])
def validate_treatment_route():
    """
    Validates a treatment plan against official Indian medical guidelines.
    Body: { diagnosis, treatment, medications, cost, context }
    Returns structured assessment with treatment_assessment, cost_assessment,
    red_flags, guideline_citations, voice_response.
    """
    data = request.get_json() or {}
    diagnosis   = (data.get("diagnosis")   or "").strip()
    treatment   = (data.get("treatment")   or "").strip()
    medications = (data.get("medications") or "").strip()
    cost        = (data.get("cost")        or "").strip()
    context     = (data.get("context")     or "").strip()

    if not diagnosis and not treatment:
        return jsonify({"error": "diagnosis or treatment is required"}), 400

    result = validate_treatment(diagnosis, treatment, medications, cost, context)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  BayMax starting on http://localhost:{port}")
    print(f"  Anthropic API : {'✓' if os.getenv('ANTHROPIC_API_KEY') else '✗ NOT SET'}")
    print(f"  Google Places : {'✓' if os.getenv('GOOGLE_PLACES_API_KEY') else '✗ NOT SET'}")
    import threading
    def _bg_index():
        n = preload_chunks()
        print(f"  ✓ Medical PDF index ready ({n} chunks)")
    threading.Thread(target=_bg_index, daemon=True).start()
    print(f"  PDF indexing started in background...")
    print()
    app.run(host="0.0.0.0", port=port, debug=True)
