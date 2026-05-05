"""Shared profile resolver for routes that need the user's `Profile`.

Reads `flask.session["profile"]` with conservative defaults (sedentary 30-year-old).
Phase 4 will add a profile entry screen that writes into the same session key.
"""

from __future__ import annotations

from flask import session

from diagnostics import Profile


def get_profile() -> Profile:
    p = session.get("profile") or {}
    return Profile(
        age=int(p.get("age", 30)),
        activity=str(p.get("activity", "sedentary")),
        exercise=str(p.get("exercise", "unknown")),
        name=str(p.get("name", "")).strip() or "user",
    )
