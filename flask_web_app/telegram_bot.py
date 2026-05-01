"""Telegram booking-card sender.

Pushes a single rich card to the user's Telegram chat with up to two inline
buttons: View on Maps and Visit Clinic Website. Used when Kirby decides to
hand off a clinic booking to the user's phone (Singpass auth is smoother
on mobile than desktop).

Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from the environment at
call time. The bot token is never logged or returned to callers; failures
degrade gracefully to a `False` return so the chat reply can still go out.
"""

from __future__ import annotations

import logging
import os

import requests

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT_SECONDS = 5

# MarkdownV2 reserved characters per Telegram Bot API. Each must be backslash-
# escaped or Telegram returns 400. The set must be complete.
_MD_V2_RESERVED = r"_*[]()~`>#+-=|{}.!"

log = logging.getLogger(__name__)


def _escape_md_v2(s: str) -> str:
    out = []
    for ch in s or "":
        if ch in _MD_V2_RESERVED:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def _looks_like_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


def send_booking_card(clinic_name: str, maps_url: str = "", website_url: str = "") -> bool:
    """Push a Telegram card for the chosen clinic.

    Both URLs are taken verbatim from the Google Places lookup that surfaced
    the clinic in chat. Telegram's Bot API requires every inline-keyboard URL
    to be a real, fully-qualified HTTP(S) URL, so the function silently drops
    a button whose URL is missing or malformed rather than send a 400.
    """
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        log.warning("telegram booking skipped: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return False

    name = (clinic_name or "Clinic").strip()
    map_url = maps_url.strip() if _looks_like_url(maps_url) else ""
    site_url = website_url.strip() if _looks_like_url(website_url) else ""

    if not map_url and not site_url:
        log.warning("telegram booking skipped: no valid maps_url or website_url for %r", name)
        return False

    text_lines = [
        "🏥 *You chose this clinic*",
        "",
        f"*{_escape_md_v2(name)}*",
        "",
        _escape_md_v2(
            "Tap a button below to see the clinic on Maps or visit its website to book. "
            "Singpass works smoothly on mobile 📱."
        ),
    ]

    keyboard: list[list[dict]] = []
    if map_url:
        keyboard.append([{"text": "📍 View on Maps", "url": map_url}])
    if site_url:
        keyboard.append([{"text": "🏥 Visit Clinic Website", "url": site_url}])

    payload = {
        "chat_id": chat_id,
        "text": "\n".join(text_lines),
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": keyboard},
    }

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as e:
        log.warning("telegram send failed: %s: %s", e.__class__.__name__, e)
        return False

    if not 200 <= resp.status_code < 300:
        body = (resp.text or "")[:300]
        log.warning("telegram send http %s: %s", resp.status_code, body)
        return False

    log.info("telegram booking card sent for %r (maps=%s, site=%s)", name, bool(map_url), bool(site_url))
    return True
