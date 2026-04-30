"""Verdict blueprint.

`GET /api/verdict` fetches the T-Display, appends a sample to the rolling
buffer, and returns the current debounced verdict envelope:

    {"ok": true,  "verdict": {...}, "profile": {...}}
    {"ok": false, "error": "<reason>"}

Profile defaults to a sedentary 30-year-old; Phase 4 will add a profile entry
screen and persist the user's choice in `flask.session`.
"""

from __future__ import annotations

import time

from flask import Blueprint, current_app, jsonify

from diagnostics import RollingBuffer, Sample, evaluate
from routes._profile import get_profile
from routes.export import record_sample
from routes.vitals import fetch_device, resolve_ip

bp = Blueprint("verdict", __name__, url_prefix="/api")

_buffer: RollingBuffer | None = None


def _get_buffer() -> RollingBuffer:
    global _buffer
    if _buffer is None:
        _buffer = RollingBuffer(current_app.config["ROLLING_WINDOW_SECONDS"])
    return _buffer


@bp.get("/verdict")
def get_verdict():
    ip, err = resolve_ip()
    if err:
        return jsonify(ok=False, error=err), 400

    timeout = current_app.config["ESP32_TIMEOUT_SECONDS"]
    payload, err, status = fetch_device(ip, timeout)
    if err:
        return jsonify(ok=False, error=err), status

    sample = Sample(ts=time.time(), bpm=int(payload["bpm"]), spo2=float(payload["spo2"]))

    buf = _get_buffer()
    buf.add(sample)
    record_sample(sample)

    profile = get_profile()
    verdict = evaluate(
        buf.snapshot(),
        profile,
        spo2_debounce_s=current_app.config["ANOMALY_DEBOUNCE_SPO2_SECONDS"],
        bpm_debounce_s=current_app.config["ANOMALY_DEBOUNCE_BPM_SECONDS"],
    )

    return jsonify(
        ok=True,
        verdict=verdict.to_dict(),
        profile={"age": profile.age, "activity": profile.activity, "exercise": profile.exercise},
        latest={"bpm": sample.bpm, "spo2": sample.spo2},
    )
