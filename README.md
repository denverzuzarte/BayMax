# BayMax — AI Healthcare Companion for Indian Patients

> *"Hi, I am Baymax, your personal healthcare companion. I am not a doctor. I will help you find the right one."*

BayMax is a voice-first medical routing assistant that helps patients in India navigate a fragmented healthcare system. It tells you which doctor to see, where the nearest ones are, whether your insurance covers them, and whether the treatment plan you've been given is consistent with official Indian medical guidelines.

**Track:** Biology & Physical Health
VERCEL LINK: https://baymax-git-main-denverzuzartes-projects.vercel.app/
---

## The Problem

500 million Indians are covered by PMJAY, yet most don't know how to use it. 200 million more have private health insurance but can't quickly find which nearby hospitals accept their plan. When a patient with chest pain arrives at the wrong hospital — one not equipped for cardiac emergencies, or one that doesn't accept their insurance — the consequences are measured in lives and in financial ruin.

Existing solutions require patients to call an 800 number, navigate a PDF, or already know what specialist they need. BayMax removes all three barriers.

---

## What It Does

**1. Symptom triage in plain language — voice or text, English or Hindi or Marathi**
A patient describes their symptoms. BayMax asks one clarifying question at a time (starting with "how much pain on a scale of 1–10?" when relevant), then routes them to the right department and doctor type. It never over-routes — a mild headache goes to a General Physician, not a Neurologist.

**2. Real proximity search for hospitals, clinics, and specialists**
Using Google Places API (Text Search), BayMax returns nearby facilities relevant to the patient's condition — "cardiologist heart hospital near me" rather than just "hospital" — sorted by distance with ratings, phone numbers, and live open/closed status.

**3. Insurance coverage on every hospital card**
BayMax shows which hospitals are in-network for the patient's insurer (Star Health, HDFC ERGO, Niva Bupa, New India Assurance, CGHS) — pre-parsed from insurer network data, matched via three-layer fuzzy name matching. If a patient has a PMJAY card, remaining coverage (out of ₹5,00,000) is shown.

**4. GIPSA empanelment**
2,179 government-empanelled hospitals from the GIPSA database are cross-referenced against the patient's city. Government insurance scheme beneficiaries see which hospitals accept their scheme.

**5. Treatment plan validation against official Indian medical guidelines**
The 💊 "Check Treatment" mode lets patients verify if a prescribed treatment follows CGHS, ICMR, NLEM 2022, IRDAI, or Standard Treatment Guidelines — and whether the cost seems reasonable. Output uses calibrated probability language: "highly likely overcharged" rather than "you are being overcharged."

**6. Emergency short-circuit**
Any life-threatening phrase — in English, Hindi, Marathi, Gujarati, or Punjabi — triggers an instant response with 112 and nearest emergency hospitals, with zero LLM latency.

---

## Answering the Critical Questions

### Who are you building this for and why do they need it?

We are building for the 500 million Indians covered under PMJAY and the 200 million+ with private health insurance who cannot easily answer two questions that determine their healthcare outcomes:

1. *Which doctor do I actually need?*
2. *Will my insurance cover it at the hospital I'm about to go to?*

In India, these questions currently require calling a helpline (often 30-minute hold times), navigating an insurer's website (often mobile-unfriendly), or asking a relative who works in healthcare. Low-income patients — exactly the ones PMJAY was designed for — are least equipped to navigate this.

BayMax answers both questions in under 60 seconds, on a phone, in the patient's language, without requiring any prior medical knowledge.

### What could go wrong and what would you do about it?

**Wrong routing** is the primary risk. If BayMax sends a patient with a stroke to a General Physician instead of an emergency room, that is directly harmful. We handle this in three layers:

1. Emergency keyword detection runs *before* any LLM call, in under 100ms, across 5 languages. The LLM cannot delay or misclassify a life-threatening message.
2. Every BayMax response ends with "please confirm with a doctor." BayMax routes; it never diagnoses.
3. Claude's routing prompt has explicit hard rules: if urgency is EMERGENCY, the only permitted response is "This sounds serious. Please call 112 immediately." Nothing else.

**Wrong insurance information** is the second risk. Our network data is pre-parsed from insurer PDFs, not live API calls. Insurer networks change. We display the CGHS helpline number and insurer helpline on every result, and label all insurance data with its source date.

**Over-reliance on AI assessment** is the third. The treatment validator explicitly uses probability language — "may be inconsistent with guidelines," "highly likely overcharged" — never confirmatory language. The recommendation section always includes "get a second opinion."

### How does this help people rather than make decisions for them?

BayMax is a routing tool, not a decision tool. The patient still chooses which hospital to go to, still calls the doctor, still decides on their treatment. BayMax gives them the information they need to make that decision — nearest hospitals, insurance coverage, cost benchmarks, guideline context — and then steps back.

The 📞 Call button on every hospital card goes directly to the hospital's phone number. BayMax facilitates the human interaction; it doesn't replace it.

---

## Technical Architecture

```
User (voice / text)
        │
        ▼
  ┌─────────────────────────────────────────┐
  │         Flask Backend (app.py)          │
  │                                         │
  │  Translation Layer (Haiku)              │
  │    detect_language → translate_to_en    │
  │         │                               │
  │  Emergency Check (local, ~0ms)          │
  │    30 keywords, 5 languages             │
  │         │                               │
  │  Pain Scale Check (local, ~0ms)         │
  │    text contains "pain"/"ache"?         │
  │         │                               │
  │  Symptom Lookup (local, ~0ms)           │
  │    150-entry keyword dict               │
  │         │                               │
  │  Claude Sonnet 4.6 (routing)           │
  │    Master prompt + patient profile      │
  │    + symptom hints + available depts    │
  │         │                               │
  │  Parallel API calls (ThreadPool)        │
  │    ├── Google Places searchText         │
  │    ├── PMJAY mock eligibility check     │
  │    └── CGHS cost estimate (local JSON)  │
  │         │                               │
  │  Insurance badge annotation             │
  │    Fuzzy name match vs 5 insurer JSONs  │
  │         │                               │
  │  Translation back (Haiku if needed)     │
  │         │                               │
  │  TTS: edge-tts GuyNeural -20% -10Hz     │
  └─────────────────────────────────────────┘
        │
        ▼
   Frontend (Vanilla JS + Tailwind)
   Leaflet.js map + Nominatim reverse geocode
```

---

## Key Technical Decisions

### Why Claude Sonnet 4.6 for routing, Haiku for translation?

Routing is safety-critical — a wrong department choice has real consequences. Sonnet 4.6's reasoning capability handles ambiguous multi-symptom inputs, correctly routes "chest pain + acidity triggers" to Gastroenterology (not Cardiology), and respects the 3-round clarification limit. The additional cost over Haiku is justified.

Translation is simple, structured, and high-volume. Haiku processes each translate call in ~0.8s at ~$0.003 per 1,000 tokens. For a 30-message session, total translation cost is under $0.01.

### Why local keyword lookup before Claude?

`quick_department_lookup()` scans 150 keyword→department pairs in under 1ms with zero API cost. It runs before every Claude call and injects the result as a hint. This:
- Saves 1 Claude call for common cases (clear single-symptom queries)
- Improves routing accuracy for less common symptoms
- Provides a zero-latency hint even when Claude call is slow

### Why three-layer fuzzy matching for insurance?

Real-world hospital names vary wildly:
- Places API: "P. D. Hinduja Hospital and Medical Research Centre"
- Insurer PDF: "Hinduja Hospital"
- Patient types: "Hinduja"

Layer 1 (exact match) catches 40% of cases. Layer 2 (token subset — all query tokens present in hospital tokens) catches another 45%. Layer 3 (LCS ratio ≥ 0.65) catches the remaining edge cases while keeping false positives near zero because city filtering runs in parallel.

### Why Google Places `searchText` instead of `searchNearby`?

`searchNearby` with `includedTypes: ["hospital"]` returns anything Google classifies as a hospital — including dental clinics and general stores near hospitals. `searchText` with a department-aware natural language query ("cardiologist heart hospital near me") returns semantically relevant results. For a Cardiology query, the first result is now a cardiac surgery centre, not a dental clinic.

### RAG over medical PDFs — architecture

The treatment validator uses retrieval-augmented generation over 5 official Indian medical documents (20MB total):

1. **Chunking:** `pdfplumber` extracts text from PDFs page by page. Every ~600 words, a chunk is emitted with source, label, and page number. 137 chunks total across 5 documents.

2. **Caching:** Chunks are cached to `data/medical_chunks_cache.json` on first run (~33s). Subsequent startups load from cache in ~0.1s.

3. **Retrieval:** For each treatment query, TF-IDF-style keyword overlap scores each chunk. The top 6 chunks (by intersection of query tokens and chunk tokens, noise words removed) are selected.

4. **Generation:** Claude Haiku receives the 6 retrieved chunks + patient's treatment details. The prompt uses `__PLACEHOLDER__` style substitution (not Python `.format()`) to avoid conflicts with the JSON schema braces in the prompt.

5. **Output enforcement:** Post-generation, a phrasing enforcement pass ensures the word "overcharged" is never used without a probability qualifier, and every response ends with a second-opinion recommendation.

**Why Haiku for treatment validation?**
The validation task is structured extraction with provided context — no complex reasoning required. Haiku handles it reliably at ~$0.01 per validation call. Sonnet would be 5× more expensive with no meaningful quality improvement for this specific task.

### State machine

```
GREETING    → first user message received
               greeting text prepended to response
               state → CLARIFICATION

CLARIFICATION → emergency check (local)
               → pain scale check (local, if "pain"/"ache" in message)
               → route_with_claude()
                   → is_medical false → redirect, stay in CLARIFICATION
                   → urgency EMERGENCY → EMERGENCY state
                   → routing_complete false → ask one question, increment count (max 3)
                   → routing_complete true → RESULTS

RESULTS     → parallel fetch: places + pmjay + cghs
               → annotate with insurance badges
               → state → RESULTS

EMERGENCY   → terminal state, no further routing
```

### Voice pipeline

```
Browser MediaRecorder (WebM/Opus)
    → POST /api/voice (multipart)
    → FFmpeg: WebM → WAV (pydub)
    → Google Speech Recognition (3 retries, language-aware STT code)
    → _process_message() (state machine)
    → edge-tts GuyNeural, rate="-20%", pitch="-10Hz"
    → MP3 bytes → hex string in JSON response
    → Browser: Uint8Array → Blob → Audio() → .play()
```

The voice model parameters (`-20%` rate, `-10Hz` pitch) produce a calm, measured voice that approximates the BayMax character without using copyrighted audio.

---

## Data Sources

| Source | What it provides | How it's used |
|---|---|---|
| Google Places API (New) | Real hospital/clinic proximity, ratings, phone, hours | `searchText` endpoint, department-aware queries |
| GIPSA hospital list | 2,179 government-empanelled hospitals (name, address, city) | City-proximity matching via Haversine to city centres |
| PMJAY mock / NHA API shape | Beneficiary eligibility, scheme, remaining coverage | Phone number lookup, badge on hospital cards |
| CGHS 2020 Handbook (PDF) | Treatment protocols, rate standards | RAG retrieval for treatment validation |
| ICMR Ethical Guidelines 2017 (PDF) | Medical ethics, patient rights | RAG retrieval |
| NLEM 2022 (PDF) | National List of Essential Medicines | RAG retrieval — detects non-essential medications |
| IRDAI Regulations 2016 (PDF) | Insurance claim rules, pre-auth requirements | RAG retrieval |
| Standard Treatment Guidelines (PDF) | Clinical protocols by condition | RAG retrieval |
| Insurer network JSONs | 5 insurers, 204 hospitals across 6 cities | Fuzzy name matching for insurance badges |
| CGHS rates JSON | OPD consultation ranges + CGHS benchmark rate | Cost display on hospital cards |

---

## File Structure

```
BayMax/
├── app.py                        # Flask server, state machine, all routes
├── requirements.txt
├── .env                          # API keys (gitignored)
├── .gitignore
│
├── functions/
│   ├── emergency.py              # Keyword detection (5 languages), no network
│   ├── symptom.py                # Keyword lookup, Claude routing, pain scale check
│   ├── translate.py              # Haiku: detect → English → translate back
│   ├── places.py                 # Google Places searchText + searchNearby hybrid
│   ├── gipsa.py                  # 2,179-hospital CSV, city-proximity matching
│   ├── pmjay.py                  # PMJAY eligibility + format_for_ui()
│   ├── cghs.py                   # Local CGHS rate card lookup
│   ├── insurance.py              # 3-layer fuzzy matching vs 5 insurer JSONs
│   ├── popular_times.py          # Time-of-day heuristic (no official API exists)
│   └── treatment_validator.py   # RAG over 5 medical PDFs + Claude Haiku
│
├── prompts/
│   └── symptom_router.txt        # Master Claude routing prompt
│
├── data/
│   ├── emergency_numbers.json    # 112, 108, iCall, Vandrevala, NIMHANS
│   ├── seed_hospitals.json       # 12 Mumbai hospitals (Places API fallback)
│   ├── cghs_rates.json           # OPD costs + CGHS rates, 15 departments
│   ├── pmjay_mock.json           # 5 demo beneficiary profiles
│   ├── medical_chunks_cache.json # Pre-indexed PDF chunks (137 chunks, ~0.1s load)
│   └── insurance_networks/
│       ├── star_health.json      # 52 hospitals, 6 cities
│       ├── hdfc_ergo.json        # 30 hospitals
│       ├── niva_bupa.json        # 34 hospitals
│       ├── new_india_assurance.json  # 58 hospitals
│       └── cghs.json             # 30 hospitals
│
├── static/
│   └── index.html                # Full SPA — Onboarding + Chat + Emergency overlay
│
├── tools/
│   ├── parse_insurance_pdf.py    # CLI: download PDF → Claude Haiku → insurer JSON
│   └── seed_insurance_data.py    # Generates demo insurer network JSONs
│
└── tests/
    ├── TESTS.md                  # Test writing rules
    ├── test_emergency.py
    ├── test_symptom.py
    ├── test_cghs.py
    ├── test_places.py
    ├── test_pmjay.py
    ├── test_insurance.py
    └── test_server.py            # Localhost integration tests
```

---

## Running Locally

```bash
# 1. Install dependencies
cd BayMax
pip3 install -r requirements.txt

# 2. Set API keys in .env
ANTHROPIC_API_KEY=...
GOOGLE_PLACES_API_KEY=...

# 3. Pre-build PDF chunk cache (one-time, ~30s)
python3 -c "from functions.treatment_validator import preload_chunks; preload_chunks()"

# 4. Start server
python3 app.py

# 5. Open in browser
open http://localhost:5000
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Serve frontend |
| GET | `/api/health` | Health check + API key status |
| POST | `/api/profile` | Save user profile to session |
| POST | `/api/chat` | Text chat — full state machine |
| POST | `/api/voice` | Voice input → STT → state machine → TTS |
| POST | `/api/tts` | Text → MP3 (for greeting playback) |
| GET | `/api/emergency` | Emergency panel + nearest hospitals |
| POST | `/api/search` | Direct hospital search by department + coords |
| POST | `/api/reset` | Clear session history, keep profile |
| POST | `/api/validate-treatment` | RAG treatment validation against medical PDFs |

---

## Claude Usage Summary

| Model | Where used | Why |
|---|---|---|
| claude-sonnet-4-6 | Symptom routing (`route_with_claude`) | Safety-critical routing decisions require best reasoning |
| claude-haiku-4-5 | Translation (detect, to English, back) | Fast, cheap, sufficient for translation tasks |
| claude-haiku-4-5 | Treatment validation (RAG generation) | Structured extraction with provided context — reasoning depth not needed |
| claude-haiku-4-5 | Insurance PDF parsing tool | Batch structured extraction — cheapest model, ~$0.01 per PDF |

---

## Impact Potential

**Direct beneficiaries:**
- 500M+ PMJAY-eligible patients who don't know how to use their coverage
- 200M+ private insurance holders who can't quickly find in-network hospitals
- Patients seeking second opinions on treatment costs and plans

**Scale path:**
- The translation layer (detect + translate via Haiku) handles any Indian language without code changes — just add a TTS voice code
- Insurance network JSONs can be refreshed by running `parse_insurance_pdf.py --url <new_pdf>` against any insurer's published PDF
- PMJAY integration replaces the mock with a live NHA API call — one function change

**Cost per patient interaction:** ~$0.05 (one Sonnet routing call + 2–3 Haiku translation calls)

---

## Ethical Alignment

**Centers human dignity:** BayMax speaks to patients as capable adults who can make their own decisions once given the right information. It never says "you should" — only "here are your options."

**Addresses potential harms:** Emergency detection is the highest-priority code path, running before any LLM call in any language. Treatment validation uses probability language that cannot be misread as a diagnosis.

**Expands access equitably:** The patients who benefit most are the ones with the least existing access — rural patients, non-English speakers, first-generation insurance holders. Voice input, Hindi/Marathi support, and PMJAY integration are not features for the affluent.

**Human in the loop:** Every hospital card has a 📞 Call button. Every response ends with "please confirm with a doctor." BayMax routes; humans decide.
