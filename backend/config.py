"""Centralized environment configuration for the Prism API.

Kept separate from main.py so every module (auth, uploads, analysis,
agents, llm, notify) can import config without triggering FastAPI app
construction or circular imports.
"""

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Comma-separated list, e.g. "http://localhost:5173,https://app.example.com"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# Gemini narrative layer (optional — analysis still works without it)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Node/Nodemailer notification microservice (optional — best-effort)
NOTIFY_SERVICE_URL = os.getenv("NOTIFY_SERVICE_URL", "http://localhost:4000/notify-report")
NOTIFY_SERVICE_API_KEY = os.getenv("NOTIFY_SERVICE_API_KEY", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
