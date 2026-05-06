"""
Treatment plan validator using RAG over 5 official Indian medical PDFs.

PDFs (sourced from CareNet knowledge_base):
  - CGHS Handbook 2020       — treatment protocols, rate standards
  - ICMR Ethical Guidelines  — medical ethics, patient rights
  - NLEM 2022                — National List of Essential Medicines
  - IRDAI Regulations 2016   — insurance claim rules, pre-auth requirements
  - Standard Treatment Guidelines — clinical protocols by condition

RAG strategy (cheap, no embeddings):
  1. PDFs are chunked into ~500-word segments at startup (one-time cost)
  2. For each query, TF-IDF-style keyword overlap ranks chunks by relevance
  3. Top 6 chunks are sent to Claude Haiku with the treatment plan
  4. Claude returns structured JSON assessment

Phrasing rules (HARD — never break):
  - Never say "you are being overcharged" — use probability language
  - Never confirm a diagnosis or wrong treatment — use "may be inconsistent with"
  - All assessments end with "verify with another doctor"
  - Cost flags: reasonable | somewhat_high | highly_likely_overcharged
  - Treatment flags: appropriate | questionable | likely_inconsistent
"""

import os, re, json, time
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

_KB_PATH = Path(__file__).parent.parent.parent / "CareNet" / "server" / "knowledge_base"

PDF_SOURCES = {
    "cghs":     ("CGHS_HandBook_28June2020.pdf",                              "CGHS 2020 Rate Card & Protocols"),
    "icmr":     ("1527507675_ICMR_Ethical_Guidelines_2017.pdf",              "ICMR Ethical Guidelines 2017"),
    "nlem":     ("nlem2022.pdf",                                               "NLEM 2022 Essential Medicines"),
    "irdai":    ("IRDAI (Third Party Administrators - Health Services) Regulations, 2016.pdf", "IRDAI 2016 Regulations"),
    "stg":      ("standard-treatment-guidelines.pdf",                          "Standard Treatment Guidelines"),
}

VALIDATION_PROMPT = """You are a medical advisor helping a patient in India understand whether their
treatment plan is appropriate and whether costs seem reasonable.

You have access to excerpts from official Indian medical guidelines below.
Use ONLY these guidelines to assess the treatment — do not use general knowledge alone.

════════════════════════════════════════
GUIDELINE EXCERPTS (from official Indian medical documents)
════════════════════════════════════════
__GUIDELINE_EXCERPTS__

════════════════════════════════════════
PATIENT'S TREATMENT DETAILS
════════════════════════════════════════
Diagnosis/Condition: __DIAGNOSIS__
Treatment prescribed: __TREATMENT__
Medications mentioned: __MEDICATIONS__
Estimated cost: __COST__
Additional context: __CONTEXT__

════════════════════════════════════════
YOUR TASK
════════════════════════════════════════

Assess the treatment plan across these four dimensions:

1. TREATMENT APPROPRIATENESS
   Compare the prescribed treatment against the guidelines.
   Use one of:
     appropriate          — aligns with standard guidelines
     questionable         — some aspects may not follow guidelines
     likely_inconsistent  — treatment appears to deviate from guidelines

2. COST ASSESSMENT (only if cost was provided)
   Compare against CGHS rate card benchmarks if available.
   Use one of:
     reasonable           — cost is within expected range
     somewhat_high        — cost is above typical range but not alarming
     highly_likely_overcharged — cost appears significantly above guidelines

3. RED FLAGS
   List specific concerns found by comparing to the guidelines.
   Maximum 3 red flags. Frame each as "may indicate" or "could suggest".
   Empty list if none.

4. GUIDELINE CITATIONS
   Cite specific documents and sections from the excerpts provided.
   E.g. "CGHS 2020 Handbook, Chapter 3 — rate for X procedure is ₹Y"

HARD PHRASING RULES — NEVER BREAK:
- NEVER write "you are being overcharged" — use "highly likely overcharged"
- NEVER write "this is the wrong treatment" — use "likely_inconsistent with guidelines"
- NEVER confirm a diagnosis — use "may be consistent with" or "could indicate"
- ALWAYS end voice_response with "I strongly recommend getting a second opinion from another doctor."
- voice_response is for TTS: max 3 sentences, no bullet points, no numbers, conversational
- If cost was not provided, set cost_assessment to null
- If no red flags found, return empty array for red_flags

RESPOND IN JSON ONLY. No preamble, no explanation outside the JSON:
{
  "treatment_assessment": "appropriate | questionable | likely_inconsistent",
  "cost_assessment": "reasonable | somewhat_high | highly_likely_overcharged | null",
  "red_flags": ["string", "string"],
  "guideline_citations": ["document: finding"],
  "recommendations": ["action for patient to take"],
  "voice_response": "string — spoken to patient via TTS",
  "reasoning": "one sentence for logs, not shown to patient"
}"""


# ─────────────────────────────────────────────────────────────
#  PDF chunking + retrieval
# ─────────────────────────────────────────────────────────────

_chunks: list[dict] | None = None
_CACHE_PATH = Path(__file__).parent.parent / "data" / "medical_chunks_cache.json"


def _load_chunks() -> list[dict]:
    global _chunks
    if _chunks is not None:
        return _chunks

    # Fast path: load from disk cache
    if _CACHE_PATH.exists():
        try:
            _chunks = json.loads(_CACHE_PATH.read_text())
            return _chunks
        except Exception:
            pass

    # Slow path: parse PDFs then cache
    try:
        import pdfplumber
    except ImportError:
        _chunks = []
        return _chunks

    all_chunks = []
    for key, (filename, label) in PDF_SOURCES.items():
        pdf_path = _KB_PATH / filename
        if not pdf_path.exists():
            continue
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                text_buffer = ""
                for page_num, page in enumerate(pdf.pages[:80]):
                    page_text = page.extract_text() or ""
                    for table in (page.extract_tables() or []):
                        for row in table:
                            if row:
                                page_text += " | ".join(str(c or "") for c in row) + "\n"
                    text_buffer += page_text + "\n"
                    if len(text_buffer.split()) >= 600:
                        all_chunks.append({
                            "source": key,
                            "label":  label,
                            "page":   page_num + 1,
                            "text":   text_buffer[:3000],
                        })
                        text_buffer = ""
                if text_buffer.strip():
                    all_chunks.append({
                        "source": key, "label": label,
                        "page": "end", "text": text_buffer[:3000],
                    })
        except Exception:
            continue

    _chunks = all_chunks
    # Save cache for next startup
    try:
        _CACHE_PATH.write_text(json.dumps(_chunks))
    except Exception:
        pass
    return _chunks


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r'\b[a-z]{3,}\b', text.lower()))


def _retrieve_chunks(query: str, top_k: int = 6) -> list[dict]:
    """TF-IDF-style retrieval: score each chunk by keyword overlap with query."""
    chunks = _load_chunks()
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return chunks[:top_k]

    scored = []
    for chunk in chunks:
        chunk_tokens = _tokenize(chunk["text"])
        overlap = len(query_tokens & chunk_tokens)
        scored.append((overlap, chunk))

    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


def _format_excerpts(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"[{i}] Source: {c['label']} (page ~{c['page']})\n"
            f"{c['text'][:800].strip()}\n"
        )
    return "\n---\n".join(parts) if parts else "(No relevant guideline excerpts found)"


# ─────────────────────────────────────────────────────────────
#  Main validation function
# ─────────────────────────────────────────────────────────────

_FALLBACK = {
    "treatment_assessment": "questionable",
    "cost_assessment":       None,
    "red_flags":             [],
    "guideline_citations":   [],
    "recommendations":       ["Please consult another doctor for a second opinion."],
    "voice_response": (
        "I wasn't able to fully analyse your treatment against the guidelines right now. "
        "I strongly recommend getting a second opinion from another doctor."
    ),
    "reasoning": "API error or no guideline chunks found",
}


def validate_treatment(
    diagnosis:   str,
    treatment:   str,
    medications: str = "",
    cost:        str = "",
    context:     str = "",
) -> dict:
    """
    Validates a treatment plan against official Indian medical guidelines.

    Args:
      diagnosis:   Patient's stated condition/diagnosis
      treatment:   Treatment plan / procedures prescribed
      medications: Medications mentioned
      cost:        Stated cost (e.g. "₹45,000")
      context:     Any additional context from the conversation

    Returns structured dict — see VALIDATION_PROMPT for schema.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {**_FALLBACK, "reasoning": "No ANTHROPIC_API_KEY set"}

    # Build query for retrieval: combine all available info
    retrieval_query = f"{diagnosis} {treatment} {medications} {context}"
    chunks = _retrieve_chunks(retrieval_query, top_k=6)
    excerpts = _format_excerpts(chunks)

    prompt = (VALIDATION_PROMPT
        .replace("__GUIDELINE_EXCERPTS__", excerpts)
        .replace("__DIAGNOSIS__",    diagnosis   or "not specified")
        .replace("__TREATMENT__",    treatment   or "not specified")
        .replace("__MEDICATIONS__",  medications or "not specified")
        .replace("__COST__",         cost        or "not provided")
        .replace("__CONTEXT__",      context     or "none")
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",   # cheapest — simple structured extraction
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$",       "", raw).strip()

        result = json.loads(raw)
        for k, v in _FALLBACK.items():
            result.setdefault(k, v)

        # Enforce phrasing rules post-hoc
        voice = result.get("voice_response", "")
        if "overcharged" in voice.lower() and "likely" not in voice.lower():
            voice = voice.replace("overcharged", "may be overcharged — though I cannot confirm this")
        if not voice.rstrip().endswith("."):
            voice = voice.rstrip() + "."
        if "second opinion" not in voice.lower():
            voice += " I strongly recommend getting a second opinion from another doctor."
        result["voice_response"] = voice

        return result

    except json.JSONDecodeError as e:
        return {**_FALLBACK, "reasoning": f"JSON parse error: {e}"}
    except Exception as e:
        return {**_FALLBACK, "reasoning": f"API error: {e}"}


def preload_chunks():
    """Call at server startup to pre-index PDFs (takes ~5s first time)."""
    chunks = _load_chunks()
    return len(chunks)
