"""Vitals proxy blueprint.

Exposes `GET /api/vitals` which fetches the ESP32 wearable's `/data` endpoint
on the local network and returns a normalised envelope:

    {"ok": true,  "data": {spo2, bpm}}
    {"ok": false, "error": "<reason>"}

The target IP comes from `Config.ESP32_IP`. A `?ip=` query string overrides it
for ad-hoc testing. The override is validated as a literal IPv4/IPv6 address to
avoid turning this endpoint into a generic SSRF gadget.

`fetch_device` is shared with `routes/verdict.py` so the rolling buffer feed
uses the same upstream call, error envelope, and field-shape guard.
"""

from __future__ import annotations

import ipaddress
import logging

import requests
from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("vitals", __name__, url_prefix="/api")

log = logging.getLogger(__name__)

_EXPECTED_KEYS = {"spo2", "bpm"}


def resolve_ip() -> tuple[str | None, str | None]:
    override = request.args.get("ip")
    if override:
        try:
            ipaddress.ip_address(override)
        except ValueError:
            return None, "invalid ip override"
        return override, None
    return current_app.config["ESP32_IP"], None


def fetch_device(ip: str, timeout: int) -> tuple[dict | None, str | None, int]:
    """Fetch `/data` from the T-Display.

    Returns (payload, error, status_code). On success: (dict, None, 200).
    On failure: (None, "<reason>", <http status to surface>).
    """
    url = f"http://{ip}/data"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except requests.Timeout:
        return None, "device timeout", 504
    except requests.ConnectionError:
        return None, "device unreachable", 502
    except ValueError:
        return None, "bad json from device", 502
    except requests.HTTPError as e:
        return None, f"device http {e.response.status_code}", 502
    except requests.RequestException as e:
        log.exception("device fetch failed")
        return None, f"request failed: {e.__class__.__name__}", 502

    if not isinstance(payload, dict) or not _EXPECTED_KEYS.issubset(payload.keys()):
        return None, "missing fields in device payload", 502

    return payload, None, 200


@bp.get("/vitals")
def get_vitals():
    ip, err = resolve_ip()
    if err:
        return jsonify(ok=False, error=err), 400

    timeout = current_app.config["ESP32_TIMEOUT_SECONDS"]
    payload, err, status = fetch_device(ip, timeout)
    if err:
        return jsonify(ok=False, error=err), status

    return jsonify(ok=True, data=payload)
