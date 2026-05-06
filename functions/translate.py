import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
#  Translation layer
#  All symptom processing happens in English.
#  These three functions are the only points where other
#  languages enter or leave the pipeline.
#
#  Uses claude-haiku-4-5 — fast and cheap for simple translation.
# ─────────────────────────────────────────────────────────────

_DETECT_PROMPT = """Detect the language of the following text.
Output only the language name in English (e.g., "Hindi", "Marathi", "Gujarati", "Punjabi", "English").
If the text is in English, mixed English, or you cannot determine, output "English".

Text: {text}"""

_TO_ENGLISH_PROMPT = """Translate the following to English.
Preserve medical terms exactly as they are.
Output only the translated text, nothing else.

Text: {user_input}"""

_TO_LANGUAGE_PROMPT = """Translate the following to {language}.
Keep it conversational and warm — this will be spoken aloud by a medical assistant.
Preserve any numbers, phone numbers, and proper nouns exactly.
Output only the translated text, nothing else.

Text: {english_response}"""


def _call(prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return ""


def detect_language(text: str) -> str:
    """
    Detects language of text. Called once at session start.
    Returns a language name string e.g. 'Hindi', 'English', 'Marathi'.
    Falls back to 'English' on empty input or API failure.
    """
    if not text or not text.strip():
        return "English"
    result = _call(_DETECT_PROMPT.format(text=text[:200]))
    return result if result else "English"


def translate_to_english(text: str) -> str:
    """
    Translates any language to English.
    Returns original text unchanged if translation fails.
    Caller should only invoke this when detected language != 'English'.
    """
    if not text or not text.strip():
        return text
    result = _call(_TO_ENGLISH_PROMPT.format(user_input=text))
    return result if result else text


def translate_to_language(english_response: str, language: str) -> str:
    """
    Translates an English response to the target language.
    Returns original English if language is 'English', empty, or translation fails.
    """
    if not language or language.strip().lower() == "english":
        return english_response
    if not english_response or not english_response.strip():
        return english_response
    result = _call(_TO_LANGUAGE_PROMPT.format(
        language=language,
        english_response=english_response,
    ))
    return result if result else english_response
