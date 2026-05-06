"""
Vercel WSGI entry point.

Voice endpoints (/api/voice) require FFmpeg which is not available on Vercel.
All text-based endpoints work normally:
  /api/chat, /api/validate-treatment, /api/search, /api/emergency, /api/tts, etc.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app   # Flask app object — Vercel serves it as a WSGI handler

# Vercel picks up `app` automatically
