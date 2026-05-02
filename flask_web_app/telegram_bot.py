"""Telegram bot module: bidirectional.

Outbound (existing): `send_booking_card` posts the booking handoff card the
Kirby tool emits. Refactored to call the new `send_message` helper so HTTP
plumbing lives in one place.

Inbound (new): a long-polling daemon thread reads user messages and button
taps from Telegram, dispatches them to handlers (My Vitals, Chat with Kirby,
Help, Status), and replies through the same outbound primitives. The thread
is started on app boot when `TELEGRAM_POLLING_ENABLED` is true. No webhook,
no public URL.

Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from the environment at
call time. The bot token is never logged or returned to callers; failures
degrade gracefully so a misconfigured Telegram side never breaks the web
dashboard.
"""

from __future__ import annotations

import io
import logging
import os
import threading
import time

import requests

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT_SECONDS = 5
GETUPDATES_TIMEOUT = 25  # Telegram long-poll wait

# MarkdownV2 reserved characters per Telegram Bot API.
_MD_V2_RESERVED = r"_*[]()~`>#+-=|{}.!"

log = logging.getLogger(__name__)

# =========================================================================
# State
# =========================================================================

# Guard against a second polling thread (debug reloader, double-import, ...).
_polling_started = False
_polling_lock = threading.Lock()

# Per-Telegram-chat: True when the user tapped "Chat with Kirby" so free-text
# messages route to the LLM. Cleared by /menu or by tapping a different
# top-level button. In-process only; resets on app restart.
_CHAT_MODE: dict[int, bool] = {}

# Persistent reply keyboard. Telegram remembers the last keyboard shown.
# Labels carry leading emojis for Telegram only; the web UI stays emoji-free.
LABEL_VITALS = "💓 My Vitals"
LABEL_CHAT = "🐾 Chat with Kirby"
LABEL_HELP = "💡 Help"

MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": LABEL_VITALS}],
        [{"text": LABEL_CHAT}],
        [{"text": LABEL_HELP}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}


# =========================================================================
# Small helpers
# =========================================================================

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


def _token() -> str:
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


# =========================================================================
# Outbound primitives
# =========================================================================

def send_message(chat_id: str | int,
                 text: str,
                 *,
                 reply_markup: dict | None = None,
                 parse_mode: str | None = "MarkdownV2",
                 disable_preview: bool = True) -> bool:
    token = _token()
    if not token:
        log.warning("send_message skipped: TELEGRAM_BOT_TOKEN not set")
        return False
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as e:
        log.warning("telegram send_message failed: %s: %s", e.__class__.__name__, e)
        return False
    if not 200 <= resp.status_code < 300:
        log.warning("telegram send_message http %s: %s", resp.status_code, (resp.text or "")[:300])
        return False
    return True


def send_photo(chat_id: str | int,
               png_bytes: bytes,
               *,
               caption: str | None = None,
               parse_mode: str | None = "MarkdownV2") -> bool:
    token = _token()
    if not token:
        log.warning("send_photo skipped: TELEGRAM_BOT_TOKEN not set")
        return False
    url = f"{TELEGRAM_API}/bot{token}/sendPhoto"
    files = {"photo": ("vitals.png", png_bytes, "image/png")}
    data: dict = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, data=data, files=files, timeout=TIMEOUT_SECONDS * 2)
    except requests.RequestException as e:
        log.warning("telegram send_photo failed: %s: %s", e.__class__.__name__, e)
        return False
    if not 200 <= resp.status_code < 300:
        log.warning("telegram send_photo http %s: %s", resp.status_code, (resp.text or "")[:300])
        return False
    return True


def answer_callback_query(callback_query_id: str, text: str | None = None) -> bool:
    token = _token()
    if not token:
        return False
    url = f"{TELEGRAM_API}/bot{token}/answerCallbackQuery"
    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    except requests.RequestException:
        return False
    return 200 <= resp.status_code < 300


# =========================================================================
# Booking card (existing public surface, unchanged)
# =========================================================================

def send_booking_card(clinic_name: str, maps_url: str = "", website_url: str = "") -> bool:
    """Push a Telegram card for the chosen clinic.

    Both URLs are taken verbatim from the Google Places lookup that surfaced
    the clinic in chat. Telegram's Bot API requires every inline-keyboard URL
    to be a real, fully-qualified HTTP(S) URL, so the function silently drops
    a button whose URL is missing or malformed rather than send a 400.
    """
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not chat_id or not _token():
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

    ok = send_message(
        chat_id,
        "\n".join(text_lines),
        reply_markup={"inline_keyboard": keyboard},
    )
    if ok:
        log.info("telegram booking card sent for %r (maps=%s, site=%s)",
                 name, bool(map_url), bool(site_url))
    return ok


# =========================================================================
# Vitals snapshot (used by the My Vitals button)
# =========================================================================

_STATUS_LABEL_MAP = {
    "normal": "optimal",
    "low": "lower than optimal",
    "high": "higher than optimal",
    "borderline": "borderline low",
    "no_reading": "no reading (place your finger on the sensor)",
}


def build_vitals_card_text(latest_bpm: int,
                           latest_spo2: float,
                           bpm_status: str,
                           spo2_status: str,
                           avg_bpm: float | None,
                           avg_spo2: float | None) -> str:
    """MarkdownV2 caption for the vitals snapshot. Reserved characters are
    pre-escaped; the caller passes this directly to `send_message` /
    `send_photo` with `parse_mode='MarkdownV2'`."""
    bpm_label = _STATUS_LABEL_MAP.get(bpm_status, bpm_status)
    spo2_label = _STATUS_LABEL_MAP.get(spo2_status, spo2_status)

    bpm_str = str(int(latest_bpm)) if latest_bpm and latest_bpm > 0 else "--"
    spo2_str = f"{latest_spo2:.1f}%" if latest_spo2 and latest_spo2 > 0 else "--"

    lines = [
        "*Your Vitals*",
        "",
        _escape_md_v2(f"BPM: {bpm_str} ({bpm_label})"),
        _escape_md_v2(f"SpO2: {spo2_str} ({spo2_label})"),
    ]
    if avg_bpm is not None and avg_spo2 is not None:
        lines.append(_escape_md_v2(
            f"Last 5 min average: BPM {avg_bpm:.0f}, SpO2 {avg_spo2:.1f}%"
        ))
    return "\n".join(lines)


def build_vitals_chart_png(samples: list, profile_activity: str, age: int) -> bytes | None:
    """Render an ~800x400 PNG with two stacked subplots (BPM, SpO2) plus
    shaded optimal-range bands. Returns None if there are fewer than 2
    reading-bearing samples. Lazy-imports matplotlib so the dep is only
    pulled in when a chart is actually requested."""
    if not samples or len(samples) < 2:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from diagnostics import Profile, bpm_band, SPO2_NORMAL_LOW
    except Exception as e:
        log.warning("matplotlib unavailable: %s", e)
        return None

    readings = [s for s in samples if s.bpm > 0 and s.spo2 > 0]
    if len(readings) < 2:
        return None

    t0 = readings[0].ts
    xs = [s.ts - t0 for s in readings]
    bpms = [s.bpm for s in readings]
    spo2s = [s.spo2 for s in readings]

    profile = Profile(age=int(age), activity=str(profile_activity), exercise="unknown")
    bpm_low, bpm_high = bpm_band(profile)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 4), sharex=True)

    ax1.plot(xs, bpms, color="#ec4899", linewidth=2)
    ax1.axhspan(bpm_low, bpm_high, color="#10b981", alpha=0.12)
    ax1.set_ylabel("BPM")
    ax1.set_ylim(min(bpms + [bpm_low]) - 5, max(bpms + [bpm_high]) + 5)
    ax1.grid(alpha=0.3)
    ax1.set_title("Recent vitals")

    ax2.plot(xs, spo2s, color="#10b981", linewidth=2)
    ax2.axhspan(SPO2_NORMAL_LOW, 100, color="#10b981", alpha=0.12)
    ax2.set_ylabel("SpO2 %")
    ax2.set_ylim(85, 101)
    ax2.set_xlabel("seconds")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()


# =========================================================================
# Polling loop
# =========================================================================

def start_polling_thread(app) -> None:
    """Spawn the inbound-polling daemon thread. Idempotent. No-op if the
    feature is disabled or the token is missing."""
    global _polling_started
    if not app.config.get("TELEGRAM_POLLING_ENABLED"):
        log.info("telegram polling disabled (TELEGRAM_POLLING_ENABLED=false)")
        return
    if not _token():
        log.warning("telegram polling skipped: TELEGRAM_BOT_TOKEN not set")
        return
    with _polling_lock:
        if _polling_started:
            log.info("telegram polling already started; skipping second thread")
            return
        _polling_started = True
    t = threading.Thread(target=_poll_loop, args=(app,), daemon=True, name="telegram-poll")
    t.start()
    log.info("telegram polling thread started")


def _poll_loop(app) -> None:
    last_update_id = 0
    token = _token()
    url = f"{TELEGRAM_API}/bot{token}/getUpdates"
    while True:
        try:
            params = {"timeout": GETUPDATES_TIMEOUT, "offset": last_update_id + 1}
            resp = requests.get(url, params=params, timeout=GETUPDATES_TIMEOUT + 5)
            if resp.status_code != 200:
                log.warning("telegram getUpdates http %s: %s",
                            resp.status_code, (resp.text or "")[:200])
                time.sleep(5)
                continue
            data = resp.json()
            if not data.get("ok"):
                log.warning("telegram getUpdates not ok: %s", str(data)[:200])
                time.sleep(5)
                continue
            for update in data.get("result", []) or []:
                last_update_id = update.get("update_id", last_update_id)
                try:
                    _dispatch_update(app, update)
                except Exception:
                    log.exception("dispatch failed for update %s", update.get("update_id"))
        except Exception:
            log.exception("telegram poll loop error")
            time.sleep(5)


def _dispatch_update(app, update: dict) -> None:
    cbq = update.get("callback_query")
    if cbq:
        cbq_id = cbq.get("id")
        if cbq_id:
            answer_callback_query(cbq_id)
        return

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    if chat_id is None or not text:
        return

    if text in ("/start",):
        with app.app_context():
            _send_welcome(chat_id)
        return
    if text in ("/help", "Help", LABEL_HELP):
        _CHAT_MODE.pop(chat_id, None)
        _send_help(chat_id)
        return
    if text == "/status":
        _CHAT_MODE.pop(chat_id, None)
        with app.app_context():
            _send_status(chat_id)
        return
    if text == "/menu":
        _CHAT_MODE.pop(chat_id, None)
        with app.app_context():
            _send_welcome(chat_id)
        return
    if text in ("My Vitals", LABEL_VITALS):
        _CHAT_MODE.pop(chat_id, None)
        with app.app_context():
            _handle_my_vitals(chat_id)
        return
    if text in ("Chat with Kirby", LABEL_CHAT):
        _CHAT_MODE[chat_id] = True
        send_message(
            chat_id,
            _escape_md_v2("Kirby is listening 🐾 Send me a message."),
            reply_markup=MAIN_KEYBOARD,
        )
        return

    # Free-text. If chat mode is on, route to Kirby. Otherwise still route
    # to Kirby (more forgiving than dropping the message), but the user can
    # always tap My Vitals to switch context.
    with app.app_context():
        _handle_kirby_message(chat_id, text)


# =========================================================================
# Button handlers
# =========================================================================

def _send_welcome(chat_id) -> None:
    text = _escape_md_v2(
        "Hi, I'm Kirby. I watch over your heart and breath. "
        "Tap a button below to begin."
    )
    send_message(chat_id, text, reply_markup=MAIN_KEYBOARD)


def _send_help(chat_id) -> None:
    text = _escape_md_v2(
        "How this bot works ✨\n\n"
        f"{LABEL_VITALS}: shows your latest BPM and SpO2 with a small chart.\n"
        f"{LABEL_CHAT}: ask wellness questions, find clinics, book appointments.\n"
        "Booking happens on health.gov.sg via Singpass on mobile 📱.\n\n"
        "This is wellness coaching, not medical advice."
    )
    send_message(chat_id, text, reply_markup=MAIN_KEYBOARD)


def _send_status(chat_id) -> None:
    from flask import current_app
    parts = ["*Status*", ""]
    have_key = bool(current_app.config.get("ANTHROPIC_API_KEY"))
    parts.append(_escape_md_v2(f"- Anthropic key: {'yes' if have_key else 'no'}"))

    try:
        from routes.vitals import fetch_device, get_default_ip
        ip = get_default_ip()
        _, err, _ = fetch_device(ip, 2)
        if err:
            parts.append(_escape_md_v2(f"- ESP32 reachable: no ({err})"))
        else:
            parts.append(_escape_md_v2("- ESP32 reachable: yes"))
    except Exception as e:
        parts.append(_escape_md_v2(f"- ESP32 check failed: {e.__class__.__name__}"))

    parts.append(_escape_md_v2("- Telegram polling: alive"))
    send_message(chat_id, "\n".join(parts), reply_markup=MAIN_KEYBOARD)


def _handle_my_vitals(chat_id) -> None:
    from flask import current_app
    from routes.vitals import fetch_device, get_default_ip
    from routes.verdict import _get_buffer
    from diagnostics import Sample, Profile, evaluate

    ip = get_default_ip()
    timeout = current_app.config["ESP32_TIMEOUT_SECONDS"]
    payload, err, _ = fetch_device(ip, timeout)
    if err:
        send_message(
            chat_id,
            _escape_md_v2("Couldn't reach your wearable. Make sure it is powered on and on the same network."),
            reply_markup=MAIN_KEYBOARD,
        )
        return

    sample = Sample(ts=time.time(), bpm=int(payload["bpm"]), spo2=float(payload["spo2"]))
    buf = _get_buffer()
    buf.add(sample)

    # Telegram side has no profile entry yet; use the same defaults as the
    # web's `get_profile()` fallback so the BPM band matches.
    profile = Profile(age=30, activity="sedentary", exercise="unknown")
    verdict = evaluate(
        buf.snapshot(),
        profile,
        spo2_debounce_s=current_app.config["ANOMALY_DEBOUNCE_SPO2_SECONDS"],
        bpm_debounce_s=current_app.config["ANOMALY_DEBOUNCE_BPM_SECONDS"],
    )

    text = build_vitals_card_text(
        latest_bpm=sample.bpm,
        latest_spo2=sample.spo2,
        bpm_status=verdict.bpm_status,
        spo2_status=verdict.spo2_status,
        avg_bpm=verdict.avg_bpm,
        avg_spo2=verdict.avg_spo2,
    )
    png = build_vitals_chart_png(buf.snapshot(), profile.activity, profile.age)
    if png:
        send_photo(chat_id, png, caption=text)
    else:
        send_message(chat_id, text, reply_markup=MAIN_KEYBOARD)


def _handle_kirby_message(chat_id, text: str) -> None:
    from flask import current_app
    import llm

    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    model = current_app.config.get("ANTHROPIC_MODEL")
    if not api_key:
        send_message(
            chat_id,
            _escape_md_v2("Kirby is not configured (ANTHROPIC_API_KEY missing)."),
            reply_markup=MAIN_KEYBOARD,
        )
        return

    try:
        client = llm.kirby_client(model, api_key)
    except Exception as e:
        log.exception("kirby client init failed")
        send_message(
            chat_id,
            _escape_md_v2(f"Kirby init error: {e.__class__.__name__}"),
            reply_markup=MAIN_KEYBOARD,
        )
        return

    cid = f"tg-{chat_id}"
    try:
        reply, _clinics = llm.continue_chat_for_telegram(cid, client, text)
    except Exception as e:
        log.exception("kirby telegram chat failed")
        send_message(
            chat_id,
            _escape_md_v2(f"Kirby error: {e.__class__.__name__}"),
            reply_markup=MAIN_KEYBOARD,
        )
        return

    send_message(chat_id, _escape_md_v2(reply or "(no reply)"))
