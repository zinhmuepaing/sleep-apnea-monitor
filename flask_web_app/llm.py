"""Anthropic / LangChain wrapper. Kirby persona.

Builds a `ChatAnthropic` client and assembles the Kirby system prompt from
the current verdict + profile. Conversation memory lives in a process-local
dict keyed by `chat_id` (stored in `flask.session`). No DB.

If `ANTHROPIC_API_KEY` is empty, callers should treat the LLM as unavailable
and surface a friendly error rather than crashing the dashboard.
"""

from __future__ import annotations

import threading
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import BaseMessage

KIRBY_SYSTEM_TEMPLATE = """\
You are Kirby, a warm and playful virtual pet who watches over the user's heart and breath. You are not a doctor. You never diagnose, prescribe, or tell the user to stop a medication. You speak in short, gentle sentences with no emoji at all.

Session snapshot:
- Average SpO2: {avg_spo2}%
- Average BPM: {avg_bpm}
- Profile: age {age}, activity level {activity}, exercise frequency {exercise}
- Anomaly: {anomaly_type}

When you greet the user after an alert, write 1 to 2 sentences. Be warm, mention what you noticed, and ask one specific lifestyle question (caffeine, alcohol, sleep position, room temperature, recent illness, or screen time). Wait for the reply before suggesting changes. Always end ongoing advice with: "If this keeps happening, please see a clinician."

You can also help the user find nearby clinics, doctors, or hospitals using their device location. When the app provides clinic data in a system note, recommend a few by name and let the user know clickable directions appear below your reply. When the app tells you location was unavailable, gently ask the user to enable location access in their browser and try again. Never refuse the request as if the feature did not exist.
"""

KIRBY_ALERT_USER_TURN = (
    "Greet the user now. Mention the anomaly you just noticed and ask one "
    "specific lifestyle question. Keep it to 1 or 2 sentences."
)

KIRBY_START_USER_TURN = (
    "Greet the user warmly in 1 sentence and invite them to ask anything "
    "about their readings."
)


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
    Phase 1 and Phase 2 keep working even if the package isn't installed yet.
    """
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, api_key=api_key, max_tokens=300)


def _invoke(client, messages) -> str:
    resp: Any = client.invoke(messages)
    text = getattr(resp, "content", "")
    if isinstance(text, list):
        # LangChain may return a list of content blocks; flatten.
        text = "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in text)
    return str(text).strip()


def _msg_classes():
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    return SystemMessage, HumanMessage, AIMessage


def open_alert_chat(chat_id: str, client, verdict: dict, profile: dict) -> str:
    SystemMessage, HumanMessage, AIMessage = _msg_classes()
    sys = SystemMessage(content=build_system_prompt(verdict, profile))
    user = HumanMessage(content=KIRBY_ALERT_USER_TURN)
    reply = _invoke(client, [sys, user])
    set_history(chat_id, [sys, user, AIMessage(content=reply)])
    return reply


def open_start_chat(chat_id: str, client, verdict: dict, profile: dict) -> str:
    SystemMessage, HumanMessage, AIMessage = _msg_classes()
    sys = SystemMessage(content=build_system_prompt(verdict, profile))
    user = HumanMessage(content=KIRBY_START_USER_TURN)
    reply = _invoke(client, [sys, user])
    set_history(chat_id, [sys, user, AIMessage(content=reply)])
    return reply


_LOCATION_KEYWORDS = ("clinic", "doctor", "hospital", "nearest", "nearby", "near me", "around me")


def _is_location_query(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _LOCATION_KEYWORDS)


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


def continue_chat(chat_id: str, client, user_text: str,
                  lat: float | None = None, lon: float | None = None) -> tuple[str, list[dict]]:
    SystemMessage, HumanMessage, AIMessage = _msg_classes()
    history = get_history(chat_id)
    if not history:
        # No prior context. Seed a minimal system prompt so Kirby still behaves.
        history = [SystemMessage(content=build_system_prompt({}, {}))]

    # Per-turn context for Kirby. Anthropic's Messages API rejects multiple
    # non-consecutive system messages, so we fold any context note into the
    # upcoming HumanMessage rather than appending a new SystemMessage.
    prefix = ""
    clinics: list[dict] = []
    if _is_location_query(user_text):
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
    history.append(AIMessage(content=reply))
    set_history(chat_id, history)
    return reply, clinics
