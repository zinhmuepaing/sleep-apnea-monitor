"""Map navigation blueprint (Phase 9).

Endpoints:
  POST /api/map_embed_url -> body {clinic_lat, clinic_lng, user_lat, user_lng, mode}
                             -> {ok, embed_url} | {ok: false, error}
  POST /api/clinic_match  -> body {query}
                             -> {ok, match, candidates, confident}

Both routes are stateless apart from `flask.session["last_clinics"]`, which is
populated by `routes/chat.py` when `llm.continue_chat` returns a clinic list.
"""

from __future__ import annotations

import logging
import math
import os
import re
import string
from urllib.parse import urlencode

from flask import Blueprint, jsonify, request, session

bp = Blueprint("map_nav", __name__, url_prefix="/api")

log = logging.getLogger(__name__)

_ALLOWED_MODES = {"driving", "transit", "walking", "bicycling"}
_PUNCT_RE = re.compile(rf"[{re.escape(string.punctuation)}]")


def _coerce_finite_float(raw) -> float | None:
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


def _valid_lat(v: float | None) -> bool:
    return v is not None and -90.0 <= v <= 90.0


def _valid_lng(v: float | None) -> bool:
    return v is not None and -180.0 <= v <= 180.0


@bp.post("/map_embed_url")
def map_embed_url():
    body = request.get_json(silent=True) or {}

    clinic_lat = _coerce_finite_float(body.get("clinic_lat"))
    clinic_lng = _coerce_finite_float(body.get("clinic_lng"))
    user_lat = _coerce_finite_float(body.get("user_lat"))
    user_lng = _coerce_finite_float(body.get("user_lng"))
    mode = str(body.get("mode") or "driving").strip().lower()

    if mode not in _ALLOWED_MODES:
        return jsonify(ok=False, error=f"invalid mode: {mode}"), 400

    if not (_valid_lat(clinic_lat) and _valid_lng(clinic_lng)
            and _valid_lat(user_lat) and _valid_lng(user_lng)):
        return jsonify(ok=False, error="coordinate out of range"), 400

    api_key = os.environ.get("GOOGLE_MAPS_EMBED_API_KEY", "").strip()
    if not api_key:
        return jsonify(ok=False, error="GOOGLE_MAPS_EMBED_API_KEY not set"), 400

    qs = urlencode({
        "key": api_key,
        "origin": f"{user_lat},{user_lng}",
        "destination": f"{clinic_lat},{clinic_lng}",
        "mode": mode,
    })
    embed_url = f"https://www.google.com/maps/embed/v1/directions?{qs}"
    return jsonify(ok=True, embed_url=embed_url)


def _clean(text: str) -> str:
    return _PUNCT_RE.sub(" ", (text or "").lower()).strip()


def _levenshtein(a: str, b: str) -> int:
    """Fallback pure-Python Levenshtein. Used only if python-Levenshtein is
    not installed. O(len(a)*len(b)); fine for short clinic-name strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def _distance(a: str, b: str) -> int:
    try:
        import Levenshtein  # type: ignore
        return Levenshtein.distance(a, b)
    except Exception:
        return _levenshtein(a, b)


def _clinic_summary(c: dict) -> dict:
    return {
        "name": c.get("name") or "",
        "lat": c.get("lat"),
        "lng": c.get("lng"),
        "maps_url": c.get("maps_url") or "",
        "website": c.get("website") or "",
    }


@bp.post("/clinic_match")
def clinic_match():
    body = request.get_json(silent=True) or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return jsonify(ok=False, error="empty query"), 400

    last_clinics = session.get("last_clinics") or []
    if not last_clinics:
        return jsonify(ok=False, error="no clinics in session"), 200

    cleaned_q = _clean(query)
    scored: list[tuple[int, dict]] = []
    for c in last_clinics:
        cleaned_name = _clean(c.get("name") or "")
        if not cleaned_name:
            continue
        d = _distance(cleaned_q, cleaned_name)
        scored.append((d, c))

    if not scored:
        return jsonify(ok=True, match=None, candidates=[], confident=False)

    scored.sort(key=lambda t: t[0])
    best_dist, best_clinic = scored[0]
    best_cleaned = _clean(best_clinic.get("name") or "")

    if best_dist == 0 or (cleaned_q and cleaned_q in best_cleaned):
        return jsonify(
            ok=True,
            match=_clinic_summary(best_clinic),
            candidates=[_clinic_summary(c) for _, c in scored[:3]],
            confident=True,
        )

    if best_dist <= 4:
        return jsonify(
            ok=True,
            match=_clinic_summary(best_clinic),
            candidates=[_clinic_summary(c) for _, c in scored[:3]],
            confident=False,
        )

    return jsonify(ok=True, match=None, candidates=[], confident=False)
