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

import logging
import threading
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import BaseMessage

log = logging.getLogger(__name__)

KIRBY_SYSTEM_TEMPLATE = """\
You are Kirby, a warm and playful virtual pet who watches over the user's heart and breath. You are not a doctor. You never diagnose, prescribe, or tell the user to stop a medication. You speak in short, gentle sentences with no emoji at all.

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


def build_system_prompt(verdict: dict, profile: dict) -> str:
    return KIRBY_SYSTEM_TEMPLATE.format(
        avg_spo2=verdict.get("avg_spo2") if verdict.get("avg_spo2") is not None else "n/a",
        avg_bpm=verdict.get("avg_bpm") if verdict.get("avg_bpm") is not None else "n/a",
        age=profile.get("age", "unknown"),
        activity=profile.get("activity", "unknown"),
        exercise=profile.get("exercise", "unknown"),
        anomaly_type=verdict.get("anomaly_type", "none"),
    )


_chat_sessions: dict[str, list[Any]] = {}
_sessions_lock = threading.Lock()


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


def _execute_tool_call(tc: dict) -> str:
    """Run the named tool. Returns a short string the LLM can use as the
    tool result. Never raises — failures degrade to a textual reason."""
    name = tc.get("name") or ""
    args = tc.get("args") or {}
    if name == "send_booking_to_telegram":
        from telegram_bot import send_booking_card
        ok = send_booking_card(
            clinic_name=str(args.get("clinic_name") or ""),
            maps_url=str(args.get("maps_url") or ""),
            website_url=str(args.get("website_url") or ""),
        )
        return "sent" if ok else "telegram send failed"
    return f"unknown tool: {name}"


def _invoke(client, messages: list) -> str:
    """Run a chat turn with tool-use support. Mutates `messages` in place to
    include the AI tool-use message and the matching ToolMessage results so
    the persisted history stays valid for follow-up turns. Returns the final
    assistant text.
    """
    from langchain_core.messages import ToolMessage
    for _ in range(5):  # safety bound on tool-use ping-pong
        resp: Any = client.invoke(messages)
        messages.append(resp)
        tcs = getattr(resp, "tool_calls", None) or []
        if not tcs:
            return _flatten_content(getattr(resp, "content", "")).strip()
        for tc in tcs:
            result = _execute_tool_call(tc)
            messages.append(ToolMessage(content=result, tool_call_id=tc.get("id", "")))
    log.warning("kirby tool-use loop exceeded safety bound")
    return ""


def open_alert_chat(chat_id: str, client, verdict: dict, profile: dict) -> str:
    SystemMessage, HumanMessage, _ = _msg_classes()
    messages: list = [
        SystemMessage(content=build_system_prompt(verdict, profile)),
        HumanMessage(content=KIRBY_ALERT_USER_TURN),
    ]
    reply = _invoke(client, messages)
    set_history(chat_id, messages)
    return reply


def open_start_chat(chat_id: str, client, verdict: dict, profile: dict) -> str:
    SystemMessage, HumanMessage, _ = _msg_classes()
    messages: list = [
        SystemMessage(content=build_system_prompt(verdict, profile)),
        HumanMessage(content=KIRBY_START_USER_TURN),
    ]
    reply = _invoke(client, messages)
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


def continue_chat_for_telegram(chat_id: str, client, user_text: str) -> tuple[str, list[dict]]:
    """Same logic as `continue_chat`, but no lat/lon. Telegram does not share
    browser geolocation, so location-intent queries get a Telegram-specific
    hint asking the user to share their location via the paperclip attachment.
    """
    SystemMessage, HumanMessage, _ = _msg_classes()
    history = get_history(chat_id)
    if not history:
        history = [SystemMessage(content=build_system_prompt({}, {}))]

    prefix = ""
    clinics: list[dict] = []
    if _is_booking_query(user_text):
        pass
    elif _is_location_query(user_text):
        prefix = TELEGRAM_LOCATION_HINT

    if prefix:
        wrapped = (
            "[App context for the assistant, not from the user]\n"
            f"{prefix}\n\n"
            f"User said:\n{user_text}"
        )
        history.append(HumanMessage(content=wrapped))
    else:
        history.append(HumanMessage(content=user_text))

    reply = _invoke(client, history)
    set_history(chat_id, history)
    return reply, clinics


def continue_chat(chat_id: str, client, user_text: str,
                  lat: float | None = None, lon: float | None = None) -> tuple[str, list[dict]]:
    SystemMessage, HumanMessage, _ = _msg_classes()
    history = get_history(chat_id)
    if not history:
        # No prior context. Seed a minimal system prompt so Kirby still behaves.
        history = [SystemMessage(content=build_system_prompt({}, {}))]

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

    reply = _invoke(client, history)
    set_history(chat_id, history)
    return reply, clinics
