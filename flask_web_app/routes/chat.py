"""Kirby chat blueprint.

Endpoints:
  POST /api/chat/alert   -> body {verdict, profile} -> Kirby's anomaly opener
  POST /api/chat/start   -> body {verdict?, profile?} -> Kirby's friendly greeting
  POST /api/chat/message -> body {text} -> Kirby's next reply

A per-tab `chat_id` is stored in `flask.session` and used as the key into the
in-memory conversation store in `llm.py`. No persistent storage.
"""

from __future__ import annotations

import logging
import math
import uuid

from flask import Blueprint, current_app, jsonify, request, session

import llm

bp = Blueprint("chat", __name__, url_prefix="/api/chat")

log = logging.getLogger(__name__)

MESSAGE_MAX_LEN = 500


def _coerce_lang(raw) -> str:
    return "zh" if str(raw or "").lower() == "zh" else "en"


def _ensure_chat_id() -> str:
    cid = session.get("chat_id")
    if not cid:
        cid = uuid.uuid4().hex
        session["chat_id"] = cid
    return cid


def _client_or_error():
    api_key = current_app.config["ANTHROPIC_API_KEY"]
    model = current_app.config["ANTHROPIC_MODEL"]
    if not api_key:
        return None, ("llm not configured (set ANTHROPIC_API_KEY in .env)", 503)
    try:
        return llm.kirby_client(model, api_key), None
    except ImportError as e:
        log.exception("langchain-anthropic not installed")
        return None, (f"missing dependency: {e.name}. run: pip install -r requirements.txt", 500)
    except Exception as e:
        log.exception("kirby client init failed")
        return None, (f"kirby init error: {e.__class__.__name__}: {e}", 500)


def _safe_invoke(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        log.exception("kirby call failed")
        return None, f"kirby error: {e.__class__.__name__}: {e}"


@bp.post("/alert")
def chat_alert():
    body = request.get_json(silent=True) or {}
    verdict = body.get("verdict") or {}
    profile = body.get("profile") or {}
    lang = _coerce_lang(body.get("lang"))

    client, err = _client_or_error()
    if err:
        msg, status = err
        return jsonify(ok=False, error=msg), status

    cid = uuid.uuid4().hex  # fresh chat for each anomaly
    session["chat_id"] = cid

    text, ferr = _safe_invoke(llm.open_alert_chat, cid, client, verdict, profile, lang)
    if ferr:
        return jsonify(ok=False, error=ferr), 502
    return jsonify(ok=True, chat_id=cid, text=text)


@bp.post("/start")
def chat_start():
    body = request.get_json(silent=True) or {}
    verdict = body.get("verdict") or {}
    profile = body.get("profile") or {}
    lang = _coerce_lang(body.get("lang"))

    client, err = _client_or_error()
    if err:
        msg, status = err
        return jsonify(ok=False, error=msg), status

    cid = _ensure_chat_id()
    text, ferr = _safe_invoke(llm.open_start_chat, cid, client, verdict, profile, lang)
    if ferr:
        return jsonify(ok=False, error=ferr), 502
    return jsonify(ok=True, chat_id=cid, text=text)


def _coerce_coord(raw) -> float | None:
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


@bp.post("/message")
def chat_message():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()

    if not text:
        return jsonify(ok=False, error="empty message"), 400
    if len(text) > MESSAGE_MAX_LEN:
        return jsonify(ok=False, error=f"message too long (max {MESSAGE_MAX_LEN} chars)"), 400

    lat = _coerce_coord(body.get("lat"))
    lon = _coerce_coord(body.get("lon"))
    lang = _coerce_lang(body.get("lang"))
    if lat is not None and not -90.0 <= lat <= 90.0:
        lat = None
    if lon is not None and not -180.0 <= lon <= 180.0:
        lon = None

    client, err = _client_or_error()
    if err:
        msg, status = err
        return jsonify(ok=False, error=msg), status

    cid = _ensure_chat_id()
    result, ferr = _safe_invoke(llm.continue_chat, cid, client, text, lat, lon, lang)
    if ferr:
        return jsonify(ok=False, error=ferr), 502
    reply, clinics = result
    if clinics:
        session["last_clinics"] = clinics
    return jsonify(ok=True, chat_id=cid, text=reply, links=clinics)
