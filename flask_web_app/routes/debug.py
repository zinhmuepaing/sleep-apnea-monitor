"""Debug helpers. Not for production.

`GET /api/clinics/test?lat=...&lon=...&q=...` calls the Google Places API
directly with the configured key and returns the raw HTTP status, request
body, and response body. Use this to confirm the key works, billing is
enabled, and Places API (New) is enabled on the project.
"""

from __future__ import annotations

import os

import requests
from flask import Blueprint, jsonify, request

from clinics import (
    FIELD_MASK,
    PLACES_NEARBY_URL,
    PLACES_TEXT_URL,
    TIMEOUT_SECONDS,
)

bp = Blueprint("debug", __name__, url_prefix="/api")


def _coerce_float(raw, default):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


@bp.get("/clinics/test")
def clinics_test():
    api_key = (os.getenv("GOOGLE_PLACES_API_KEY") or "").strip()
    if not api_key:
        return jsonify(ok=False, error="GOOGLE_PLACES_API_KEY missing in .env"), 500

    # Defaults: Simei MRT, Singapore.
    lat = _coerce_float(request.args.get("lat"), 1.3434)
    lon = _coerce_float(request.args.get("lon"), 103.9536)
    query = (request.args.get("q") or "clinic").strip()
    radius = _coerce_float(request.args.get("radius_m"), 5000.0)

    text_body = {
        "textQuery": query,
        "maxResultCount": 5,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius,
            }
        },
    }
    nearby_body = {
        "includedTypes": ["doctor", "hospital"],
        "maxResultCount": 5,
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    def call(url, body):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT_SECONDS)
            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text[:1000]}
            return {"status": resp.status_code, "body": data}
        except requests.RequestException as e:
            return {"status": 0, "error": f"{e.__class__.__name__}: {e}"}

    return jsonify(
        ok=True,
        api_key_prefix=api_key[:6] + "..." + api_key[-4:],
        params={"lat": lat, "lon": lon, "q": query, "radius_m": radius},
        text_search={"request": text_body, "response": call(PLACES_TEXT_URL, text_body)},
        nearby_search={"request": nearby_body, "response": call(PLACES_NEARBY_URL, nearby_body)},
    )
