"""Environment and configuration loader.

Loads `.env` from the project root (one level above `flask_web_app/`) so a
single `.env` file serves both the Flask app and any sibling tooling. Secrets
are never hardcoded; missing values fall back to safe development defaults.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

log = logging.getLogger(__name__)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("Env %s=%r is not an int. Using default %d.", name, raw, default)
        return default


class Config:
    # Flask
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or "dev-only-do-not-use-in-prod"

    # ESP32
    ESP32_IP = os.getenv("ESP32_IP", "192.168.1.50")
    ESP32_TIMEOUT_SECONDS = _int("ESP32_TIMEOUT_SECONDS", 2)

    # Anthropic (Kirby persona). Default model is Claude Haiku 4.5.
    # Official IDs: alias `claude-haiku-4-5`, snapshot `claude-haiku-4-5-20251001`.
    ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY", "") or "").strip()
    ANTHROPIC_MODEL = (os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5") or "").strip()

    # Google Places API (New) for nearby clinic / hospital lookup.
    GOOGLE_PLACES_API_KEY = (os.getenv("GOOGLE_PLACES_API_KEY", "") or "").strip()

    # Behaviour
    POLLING_INTERVAL_MS = _int("POLLING_INTERVAL_MS", 1000)
    ROLLING_WINDOW_SECONDS = _int("ROLLING_WINDOW_SECONDS", 300)
    ANOMALY_DEBOUNCE_SPO2_SECONDS = _int("ANOMALY_DEBOUNCE_SPO2_SECONDS", 30)
    ANOMALY_DEBOUNCE_BPM_SECONDS = _int("ANOMALY_DEBOUNCE_BPM_SECONDS", 60)


if Config.FLASK_ENV != "development" and Config.SECRET_KEY == "dev-only-do-not-use-in-prod":
    log.warning("FLASK_SECRET_KEY is unset outside development. Set it in .env.")
