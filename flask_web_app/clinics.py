"""Nearby healthcare lookup via Google Places API (New).

Uses `places:searchNearby` with `includedTypes=['doctor', 'hospital']` ranked
by distance from the user. Returns the closest few with name, address,
distance, and the canonical Google Maps URL for direct directions.

Reads `GOOGLE_PLACES_API_KEY` from the environment (loaded from `.env` by
`config.py`). If the key is missing or the request fails, returns an empty
list and logs a warning so the caller can surface a graceful message.
"""

from __future__ import annotations

import logging
import math
import os

import requests

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
TIMEOUT_SECONDS = 8

# Field mask: only ask Google for the fields we render. Required by the
# Places API (New) and keeps the billing dimension narrow.
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.googleMapsUri",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.primaryType",
])

log = logging.getLogger(__name__)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _request_places(url: str, body: dict, api_key: str) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return (resp.json() or {}).get("places", []) or []
    except requests.HTTPError as e:
        body_text = getattr(e.response, "text", "") if e.response is not None else ""
        log.warning("places api http %s: %s", getattr(e.response, "status_code", "?"), body_text[:300])
        return []
    except requests.RequestException as e:
        log.warning("places api request failed: %s", e)
        return []
    except ValueError:
        log.warning("places api returned non-json")
        return []


def _clean_query(user_query: str) -> str:
    """Strip filler words from the user's chat message so the Places Text
    Search query is closer to what Google indexes."""
    q = (user_query or "").strip().lower()
    for filler in (
        "help me find", "can you find", "could you find", "please find",
        "find me", "find any", "find", "show me", "i need", "looking for",
        "where are the", "where is the", "where's the", "where are",
        "what are the", "what is the", "any", "some",
    ):
        if q.startswith(filler + " "):
            q = q[len(filler) + 1:]
            break
    if not q:
        return "clinic"
    if not any(kw in q for kw in ("clinic", "doctor", "hospital", "polyclinic", "gp ", "medical")):
        q = f"clinic {q}".strip()
    return q


def find_clinics(user_query: str = "clinic",
                 lat: float | None = None,
                 lon: float | None = None,
                 radius_m: int = 5000,
                 limit: int = 5) -> list[dict]:
    """Look up clinics, doctors, or hospitals via Google Places API (New).

    Primary path is Text Search so natural-language queries like
    "clinics in Singapore" or "polyclinic Simei" work. If lat/lon are
    provided, results are biased toward that circle so "near me" calls
    return nearby places first. With no coords, Google falls back on the
    place names mentioned in the query itself.
    """
    api_key = (os.getenv("GOOGLE_PLACES_API_KEY") or "").strip()
    if not api_key:
        log.warning("GOOGLE_PLACES_API_KEY is not set; clinic lookup disabled")
        return []

    query = _clean_query(user_query)
    count = min(max(limit, 1), 20)
    radius = float(min(max(radius_m, 1), 50000))

    text_body: dict = {
        "textQuery": query,
        "maxResultCount": count,
    }
    if lat is not None and lon is not None:
        text_body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius,
            }
        }

    log.info("places text search: query=%r bias=%s", query, "yes" if "locationBias" in text_body else "no")
    places = _request_places(PLACES_TEXT_URL, text_body, api_key)

    # Secondary attempt: if the user wanted nearby results and Text Search
    # came up empty, try Nearby Search by distance over the medical types.
    if not places and lat is not None and lon is not None:
        nearby_body = {
            "includedTypes": ["doctor", "hospital"],
            "maxResultCount": count,
            "rankPreference": "DISTANCE",
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": radius,
                }
            },
        }
        log.info("places nearby fallback at (%.4f, %.4f) r=%.0fm", lat, lon, radius)
        places = _request_places(PLACES_NEARBY_URL, nearby_body, api_key)

    items: list[dict] = []
    for p in places:
        loc = p.get("location") or {}
        elat, elon = loc.get("latitude"), loc.get("longitude")
        if elat is None or elon is None:
            continue
        name_obj = p.get("displayName") or {}
        fallback_url = f"https://www.google.com/maps/dir/?api=1&destination={elat},{elon}"
        distance_m = (
            int(_haversine_m(lat, lon, float(elat), float(elon)))
            if lat is not None and lon is not None else None
        )
        items.append({
            "name": name_obj.get("text") or "Unnamed clinic",
            "amenity": p.get("primaryType") or "clinic",
            "address": p.get("formattedAddress") or "",
            "distance_m": distance_m,
            "maps_url": p.get("googleMapsUri") or fallback_url,
            "website": p.get("websiteUri") or "",
            "phone": p.get("nationalPhoneNumber") or "",
        })

    if lat is not None and lon is not None:
        items.sort(key=lambda x: x["distance_m"] if x["distance_m"] is not None else float("inf"))

    return items[:limit]


# Backwards-compatible alias retained for any older callers.
def find_nearby(lat: float, lon: float, radius_m: int = 5000, limit: int = 5) -> list[dict]:
    return find_clinics("clinic", lat, lon, radius_m, limit)
