"""Profile endpoint: captures Name, Age, and Activity from the onboarding modal.

`GET  /api/profile`  -> {ok: true, set: bool, profile: {name, age, activity}}
`POST /api/profile`  -> persists JSON {name, age, activity} into the Flask session
                        cookie. Validates: name 1-60 chars, age 1-120, activity
                        in BPM_TABLE keys.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from diagnostics import BPM_TABLE

bp = Blueprint("profile", __name__, url_prefix="/api")

NAME_MAX = 60
AGE_MIN, AGE_MAX = 1, 120


@bp.get("/profile")
def get_profile_state():
    p = session.get("profile") or {}
    is_set = bool(p.get("name") and p.get("age") and p.get("activity"))
    return jsonify({
        "ok": True,
        "set": is_set,
        "profile": {
            "name": p.get("name", ""),
            "age": p.get("age"),
            "activity": p.get("activity", ""),
        },
    })


@bp.post("/profile")
def save_profile():
    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name", "")).strip()
    if not name or len(name) > NAME_MAX:
        return jsonify({"ok": False, "error": "Name must be 1 to 60 characters."}), 400

    try:
        age = int(payload.get("age"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Age must be an integer."}), 400
    if not (AGE_MIN <= age <= AGE_MAX):
        return jsonify({"ok": False, "error": f"Age must be between {AGE_MIN} and {AGE_MAX}."}), 400

    activity = str(payload.get("activity", "")).strip()
    if activity not in BPM_TABLE:
        return jsonify({"ok": False, "error": "Activity is not a valid level."}), 400

    session["profile"] = {
        "name": name,
        "age": age,
        "activity": activity,
        "exercise": session.get("profile", {}).get("exercise", "unknown"),
    }
    session.permanent = False  # tied to browser session lifetime
    return jsonify({"ok": True})
