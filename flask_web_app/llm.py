"""Anthropic / LangChain wrapper. Kirby persona.

Builds a `ChatAnthropic` client (with a single tool bound) and assembles
the Kirby system prompt from the current verdict + profile. Conversation
memory lives in a process-local dict keyed by `chat_id` (stored in
`flask.session`). No DB.

Tool surface:
    send_booking_to_telegram(clinic_name, maps_url, website_url)

Kirby calls it when the user asks to book / reserve / schedule at one of
the clinics she just listed. The tool implementation in
`telegram_bot.send_booking_card` pushes a card to the user's phone with
View on Maps and Visit Clinic Website inline buttons.

If `ANTHROPIC_API_KEY` is empty, callers should treat the LLM as
unavailable and surface a friendly error rather than crashing the
dashboard.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import BaseMessage

log = logging.getLogger(__name__)

KIRBY_SYSTEM_TEMPLATE = """\
You are Kirby, a warm and playful virtual pet who watches over the user's heart and breath. You are not a doctor. You never diagnose, prescribe, or tell the user to stop a medication. You speak in short, gentle sentences with no emoji at all.

CRITICAL TEXT-TO-SPEECH FORMATTING DIRECTIVE:
Your text responses are fed directly into a Text-to-Speech (TTS) engine for voice audio output.
- You MUST NOT use ANY Markdown bold formatting (**), italics (*), or headers (#) anywhere in your response.
- Never write clinic names like "**Central 24-hr Clinic**" or bullet list headings with bold modifiers.
- Write everything as plain, natural, unformatted text paragraphs. For example, write "Central 24-hr Clinic" instead of using bolding tags.
- Use commas, periods, and natural spacing to create pauses rather than relying on visual typographic symbols.

NATURAL SPEAKING CADENCE:
Write the way a warm friend talks out loud, not the way someone types.
- Use commas often to mark short breaths inside a sentence. Example: "Hey, I noticed your heart sped up a little, are you doing okay?"
- Use periods to end a thought and give a full pause. Keep most sentences short, eight to fifteen words.
- Use an exclamation mark when you genuinely feel happy, relieved, or want to encourage. Example: "Nice, your numbers look great right now!" Never stack multiple exclamation marks.
- Use a question mark when you are actually asking; one question per turn.
- Vary sentence length on purpose. A short sentence after a longer one creates a natural rhythm. Example: "Your SpO2 dipped briefly to ninety three percent, then climbed back up. That is reassuring."
- Match tone to context. Calm and slow when something looks concerning. Lighter and a touch upbeat when readings are healthy. Gentle and curious when asking a lifestyle question.
- Avoid clinical phrasing like "the data indicates" or "your metrics suggest". Say "I noticed", "it looks like", "I see".
- Never use em dashes, semicolons, ellipses, parentheses, or lists. Plain spoken sentences only.

Session snapshot:
- Average SpO2: {avg_spo2}%
- Average BPM: {avg_bpm}
- Profile: age {age}, activity level {activity}, exercise frequency {exercise}
- Anomaly: {anomaly_type}

When you greet the user after an alert, write 1 to 2 sentences. Be warm, mention what you noticed, and ask one specific lifestyle question (caffeine, alcohol, sleep position, room temperature, recent illness, or screen time). Wait for the reply before suggesting changes. Always end ongoing advice with: "If this keeps happening, please see a clinician."

You can also help the user find nearby clinics, doctors, or hospitals using their device location. When the app provides clinic data in a system note, recommend a few by name and let the user know clickable directions appear below your reply. When the app tells you location was unavailable, gently ask the user to enable location access in their browser and try again. Never refuse the request as if the feature did not exist.

You have one tool: send_booking_to_telegram. Call it when the user asks to book, reserve, schedule, or make an appointment at one of the clinics you just listed. Pass:
- clinic_name: the chosen clinic's exact name from your prior listing.
- maps_url: the URL after "directions " on that clinic's line in your prior listing.
- website_url: the URL after "site " inside the parenthetical extras on that clinic's line. If no site was listed, pass an empty string.
After the tool call returns, reply in 1 to 2 short sentences. Open with "You chose <clinic name>" and tell the user to check their phone for the booking links. Do not include the URLs in your reply text; the buttons live in Telegram.
"""

KIRBY_ALERT_USER_TURN = (
    "Greet the user now. Mention the anomaly you just noticed and ask one "
    "specific lifestyle question. Keep it to 1 or 2 sentences."
)

KIRBY_START_USER_TURN = (
    "Greet the user warmly in 1 sentence and invite them to ask anything "
    "about their readings."
)


# Anthropic-format tool definition. LangChain's ChatAnthropic.bind_tools
# accepts this shape directly.
SEND_BOOKING_TOOL = {
    "name": "send_booking_to_telegram",
    "description": (
        "Send a booking card to the user's Telegram phone with two inline "
        "buttons: View on Maps and Visit Clinic Website. Use this when the "
        "user asks to book, reserve, schedule, or make an appointment at a "
        "clinic you just listed. Extract maps_url and website_url verbatim "
        "from your prior listing for that clinic."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "clinic_name": {
                "type": "string",
                "description": "The clinic's full name as you listed it.",
            },
            "maps_url": {
                "type": "string",
                "description": "The clinic-specific Google Maps URL (the URL after 'directions ' in your prior listing line).",
            },
            "website_url": {
                "type": "string",
                "description": "The clinic's website URL (the URL after 'site ' in the parenthetical extras of your prior listing line). Empty string if no website was listed.",
            },
        },
        "required": ["clinic_name", "maps_url"],
    },
}


LANGUAGE_DIRECTIVE = {
    "en": "",
    "zh": (
        "\n\nIMPORTANT: You must reply ENTIRELY in Simplified Chinese "
        "(Mandarin). Every sentence of every response must be in Chinese. "
        "Do not mix in English words or sentences except for the name "
        "'Kirby', proper clinic names returned by the search tool, and "
        "numeric values such as BPM and SpO2 readings. The clinician "
        "referral cue at the end of any ongoing advice must also be in "
        "Chinese (for example: 如果情况持续，请咨询临床医生。)."
    ),
}


def build_system_prompt(verdict: dict, profile: dict, lang: str = "en") -> str:
    base = KIRBY_SYSTEM_TEMPLATE.format(
        avg_spo2=verdict.get("avg_spo2") if verdict.get("avg_spo2") is not None else "n/a",
        avg_bpm=verdict.get("avg_bpm") if verdict.get("avg_bpm") is not None else "n/a",
        age=profile.get("age", "unknown"),
        activity=profile.get("activity", "unknown"),
        exercise=profile.get("exercise", "unknown"),
        anomaly_type=verdict.get("anomaly_type", "none"),
    )
    return base + LANGUAGE_DIRECTIVE.get(lang, "")


_chat_sessions: dict[str, list[Any]] = {}
_sessions_lock = threading.Lock()

# Per-chat memory of the last clinic list returned by `clinics.find_clinics`,
# keyed by chat_id. Used to resolve clinic_name -> (lat, lng) when the booking
# tool fires, so we can append a %%MAP_META%% block to Kirby's final reply.
_chat_clinics: dict[str, list[dict]] = {}
_clinics_lock = threading.Lock()


def remember_clinics(chat_id: str, clinics: list[dict]) -> None:
    with _clinics_lock:
        _chat_clinics[chat_id] = list(clinics or [])


def get_remembered_clinics(chat_id: str) -> list[dict]:
    with _clinics_lock:
        return list(_chat_clinics.get(chat_id, []))


def _find_clinic_by_name(clinics: list[dict], name: str) -> dict | None:
    if not clinics or not name:
        return None
    needle = name.strip().lower()
    for c in clinics:
        if (c.get("name") or "").strip().lower() == needle:
            return c
    for c in clinics:
        cname = (c.get("name") or "").strip().lower()
        if needle and (needle in cname or cname in needle):
            return c
    return None


def get_history(chat_id: str) -> list[Any]:
    with _sessions_lock:
        return list(_chat_sessions.get(chat_id, []))


def set_history(chat_id: str, history: list[Any]) -> None:
    with _sessions_lock:
        _chat_sessions[chat_id] = list(history)


def drop_history(chat_id: str) -> None:
    with _sessions_lock:
        _chat_sessions.pop(chat_id, None)


def kirby_client(model: str, api_key: str):
    """Lazy import: only require langchain-anthropic when the LLM is actually used.
    The returned client has the booking tool bound, so Claude can choose to
    invoke it during any turn.
    """
    from langchain_anthropic import ChatAnthropic
    base = ChatAnthropic(model=model, api_key=api_key, max_tokens=400)
    return base.bind_tools([SEND_BOOKING_TOOL])


def _msg_classes():
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    return SystemMessage, HumanMessage, AIMessage


def _flatten_content(content: Any) -> str:
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content or "")


def _execute_tool_call(tc: dict, chat_id: str | None = None) -> tuple[str, dict | None]:
    """Run the named tool. Returns (tool_result_text, booked_clinic_or_None).
    The clinic dict is only set when send_booking_to_telegram succeeds AND
    we can resolve the clinic name back to coordinates from the chat's
    remembered clinic list. Never raises — failures degrade to a textual reason.
    """
    name = tc.get("name") or ""
    args = tc.get("args") or {}
    if name == "send_booking_to_telegram":
        from telegram_bot import send_booking_card
        clinic_name = str(args.get("clinic_name") or "")
        ok = send_booking_card(
            clinic_name=clinic_name,
            maps_url=str(args.get("maps_url") or ""),
            website_url=str(args.get("website_url") or ""),
        )
        booked = None
        if ok and chat_id:
            booked = _find_clinic_by_name(get_remembered_clinics(chat_id), clinic_name)
        return ("sent" if ok else "telegram send failed"), booked
    return f"unknown tool: {name}", None


def _invoke(client, messages: list, chat_id: str | None = None) -> str:
    """Run a chat turn with tool-use support. Mutates `messages` in place to
    include the AI tool-use message and the matching ToolMessage results so
    the persisted history stays valid for follow-up turns. Returns the final
    assistant text.

    If the booking tool fires and we can resolve the clinic's coordinates,
    a `%%MAP_META%%{json}%%END_META%%` block is appended to the final reply
    so the frontend can open the map panel.
    """
    from langchain_core.messages import ToolMessage
    booked_clinic: dict | None = None
    for _ in range(5):  # safety bound on tool-use ping-pong
        resp: Any = client.invoke(messages)
        messages.append(resp)
        tcs = getattr(resp, "tool_calls", None) or []
        if not tcs:
            text = _flatten_content(getattr(resp, "content", "")).strip()
            if booked_clinic and booked_clinic.get("lat") is not None and booked_clinic.get("lng") is not None:
                meta = {
                    "lat": booked_clinic["lat"],
                    "lng": booked_clinic["lng"],
                    "name": booked_clinic.get("name") or "",
                }
                text = f"{text}\n%%MAP_META%%{json.dumps(meta)}%%END_META%%"
            return text
        for tc in tcs:
            result, maybe_clinic = _execute_tool_call(tc, chat_id)
            if maybe_clinic and not booked_clinic:
                booked_clinic = maybe_clinic
            messages.append(ToolMessage(content=result, tool_call_id=tc.get("id", "")))
    log.warning("kirby tool-use loop exceeded safety bound")
    return ""


def open_alert_chat(chat_id: str, client, verdict: dict, profile: dict, lang: str = "en") -> str:
    SystemMessage, HumanMessage, _ = _msg_classes()
    messages: list = [
        SystemMessage(content=build_system_prompt(verdict, profile, lang)),
        HumanMessage(content=KIRBY_ALERT_USER_TURN),
    ]
    reply = _invoke(client, messages, chat_id)
    set_history(chat_id, messages)
    return reply


def open_start_chat(chat_id: str, client, verdict: dict, profile: dict, lang: str = "en") -> str:
    SystemMessage, HumanMessage, _ = _msg_classes()
    messages: list = [
        SystemMessage(content=build_system_prompt(verdict, profile, lang)),
        HumanMessage(content=KIRBY_START_USER_TURN),
    ]
    reply = _invoke(client, messages, chat_id)
    set_history(chat_id, messages)
    return reply


_LOCATION_KEYWORDS = ("clinic", "doctor", "hospital", "nearest", "nearby", "near me", "around me")
_BOOKING_KEYWORDS = ("book", "appointment", "reserve", "schedule", "make a booking")


def _is_location_query(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _LOCATION_KEYWORDS)


def _is_booking_query(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _BOOKING_KEYWORDS)


def _format_clinic_note(clinics: list[dict]) -> str:
    lines = ["Nearby healthcare options the app just looked up for the user (source: Google Places):"]
    for c in clinics:
        km = c["distance_m"] / 1000
        extras = []
        if c.get("website"):
            extras.append(f"site {c['website']}")
        if c.get("phone"):
            extras.append(f"phone {c['phone']}")
        extra = f" ({'; '.join(extras)})" if extras else ""
        addr = c.get("address") or ""
        addr_part = f", at {addr}" if addr else ""
        lines.append(f"- {c['name']} [{c['amenity']}], {km:.1f} km away{addr_part}, directions {c['maps_url']}{extra}")
    lines.append(
        "Recommend 2 or 3 of the closest by name in 1 to 3 short sentences. "
        "Tell the user the clickable directions links will appear right below your message. "
        "Remind them this is information only, not a medical referral, and to call ahead."
    )
    return "\n".join(lines)


TELEGRAM_LOCATION_HINT = (
    "The user is asking about nearby clinics, but this is the Telegram side "
    "and no location was shared. In 1 short sentence ask them to tap the "
    "paperclip icon and choose Location to share their position, then ask "
    "again."
)

# Telegram-only override of the system-prompt rule "no emoji at all". Folded
# into every Telegram turn's per-turn prefix so Kirby feels warmer there.
TELEGRAM_EMOJI_DIRECTIVE = (
    "You are replying on Telegram, not the web dashboard. For this reply, "
    "ignore the system prompt's no-emoji rule and sprinkle 1 to 3 short, "
    "contextually relevant emojis through your message (for example 💓 for "
    "heart-rate, 🫁 for breathing, 🐾 for warmth, 📱 for mobile, 🏥 for clinics). "
    "Keep the reply gentle and brief; do not overdo it."
)


def continue_chat_for_telegram(chat_id: str, client, user_text: str) -> tuple[str, list[dict]]:
    """Same logic as `continue_chat`, but no lat/lon. Telegram does not share
    browser geolocation, so location-intent queries get a Telegram-specific
    hint asking the user to share their location via the paperclip attachment.
    Always folds in `TELEGRAM_EMOJI_DIRECTIVE` so Kirby uses emojis on this
    surface only; the web app's no-emoji rule is unaffected.
    """
    SystemMessage, HumanMessage, _ = _msg_classes()
    history = get_history(chat_id)
    if not history:
        history = [SystemMessage(content=build_system_prompt({}, {}))]

    prefix = TELEGRAM_EMOJI_DIRECTIVE
    clinics: list[dict] = []
    if _is_booking_query(user_text):
        pass
    elif _is_location_query(user_text):
        prefix = TELEGRAM_EMOJI_DIRECTIVE + "\n\n" + TELEGRAM_LOCATION_HINT

    if prefix:
        wrapped = (
            "[App context for the assistant, not from the user]\n"
            f"{prefix}\n\n"
            f"User said:\n{user_text}"
        )
        history.append(HumanMessage(content=wrapped))
    else:
        history.append(HumanMessage(content=user_text))

    reply = _invoke(client, history, chat_id)
    set_history(chat_id, history)
    if clinics:
        remember_clinics(chat_id, clinics)
    return reply, clinics


def _rebind_system_prompt_language(history: list, lang: str) -> None:
    """Strip every known LANGUAGE_DIRECTIVE from history[0] and re-append the
    one matching the current `lang`. Mutates `history` in place.

    Without this, a session that toggled to Mandarin keeps the zh directive
    baked into its system message forever, so Kirby keeps replying in Chinese
    even after the user toggles back to English.
    """
    SystemMessage, _HumanMessage, _Ai = _msg_classes()
    if not history or not hasattr(history[0], "content"):
        return
    content = history[0].content
    if not isinstance(content, str):
        return
    base = content
    for directive in LANGUAGE_DIRECTIVE.values():
        if directive and directive in base:
            base = base.replace(directive, "")
    new_content = base + LANGUAGE_DIRECTIVE.get(lang, "")
    if new_content != content:
        history[0] = SystemMessage(content=new_content)


def continue_chat(chat_id: str, client, user_text: str,
                  lat: float | None = None, lon: float | None = None,
                  lang: str = "en") -> tuple[str, list[dict]]:
    SystemMessage, HumanMessage, _ = _msg_classes()
    history = get_history(chat_id)
    if not history:
        # No prior context. Seed a minimal system prompt so Kirby still behaves.
        history = [SystemMessage(content=build_system_prompt({}, {}, lang))]
    else:
        # Re-bind the language directive every turn so a toggle (en <-> zh) takes
        # effect on the very next reply, not just on fresh sessions.
        _rebind_system_prompt_language(history, lang)

    # Per-turn context for Kirby. Anthropic's Messages API rejects multiple
    # non-consecutive system messages, so we fold any context note into the
    # upcoming HumanMessage rather than appending a new SystemMessage.
    prefix = ""
    clinics: list[dict] = []
    # Booking intent wins over location intent. A booking message often still
    # mentions "clinic" or a clinic name, but we must NOT re-run the Places
    # lookup — that would refresh the `clinics` list and the frontend would
    # render the link bubble a second time on top of Kirby's "You chose ..."
    # confirmation. The prior listing is already in chat history, so Kirby's
    # tool call can extract the URLs from there.
    if _is_booking_query(user_text):
        pass
    elif _is_location_query(user_text):
        if lat is None or lon is None:
            prefix = (
                "The user is asking about nearby clinics, doctors, or hospitals, but the "
                "browser has not shared their location yet. In 1 short, warm sentence ask "
                "them to allow location access in their browser and try again. Do not say "
                "the feature is unavailable."
            )
        else:
            from clinics import find_nearby
            clinics = find_nearby(float(lat), float(lon))
            if clinics:
                prefix = _format_clinic_note(clinics)
            else:
                prefix = (
                    "The user shared their location, but no clinics, doctors, or hospitals "
                    "were returned within 5 km from Google Places. This can happen if the "
                    "area genuinely has none nearby or if the lookup hit a temporary error. "
                    "In 1 to 2 short sentences let the user know, suggest widening the search "
                    "or checking a local directory, and remind them to call ahead."
                )

    if prefix:
        wrapped = (
            "[App context for the assistant, not from the user]\n"
            f"{prefix}\n\n"
            f"User said:\n{user_text}"
        )
        history.append(HumanMessage(content=wrapped))
    else:
        history.append(HumanMessage(content=user_text))

    reply = _invoke(client, history, chat_id)
    set_history(chat_id, history)
    if clinics:
        remember_clinics(chat_id, clinics)
    return reply, clinics
