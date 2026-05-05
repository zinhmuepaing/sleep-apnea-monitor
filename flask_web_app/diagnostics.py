"""Phase 2 threshold logic and rolling buffer.

Pure module. No Flask imports. Evaluates BPM and SpO2 only; movement-based
restless detection is deferred until the firmware emits `movement` again.

Anomaly priority (highest first): spo2_low > spo2_borderline > bpm_low > bpm_high > none.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Sequence

SPO2_BORDERLINE_LOW = 92  # below this is "low"
SPO2_NORMAL_LOW = 95      # at or above this is "normal"

# Activity key -> {low, high_under_20, high_20_plus}.
BPM_TABLE: dict[str, dict[str, int]] = {
    "very_active":       {"low": 45, "high_under_20": 90,  "high_20_plus": 85},
    "moderately_active": {"low": 50, "high_under_20": 95,  "high_20_plus": 90},
    "lightly_active":    {"low": 55, "high_under_20": 100, "high_20_plus": 95},
    "sedentary":         {"low": 60, "high_under_20": 105, "high_20_plus": 100},
}

ACTIVITY_DEFAULT = "sedentary"


@dataclass(frozen=True)
class Profile:
    age: int
    activity: str   # one of BPM_TABLE keys
    exercise: str   # free-text label, surfaced to the LLM only
    name: str = "user"   # captured by the onboarding modal; used for CSV labelling


@dataclass(frozen=True)
class Sample:
    ts: float       # epoch seconds
    bpm: int
    spo2: float


@dataclass(frozen=True)
class SessionVerdict:
    spo2_status: str       # normal | borderline | low | no_reading
    bpm_status: str        # normal | high | low | no_reading
    spo2_anomaly: bool     # debounced
    bpm_anomaly: bool      # debounced
    anomaly_type: str      # spo2_low | spo2_borderline | bpm_high | bpm_low | none
    avg_spo2: float | None
    avg_bpm: float | None
    window_seconds: int
    sample_count: int

    def to_dict(self) -> dict:
        return {
            "spo2_status": self.spo2_status,
            "bpm_status": self.bpm_status,
            "spo2_anomaly": self.spo2_anomaly,
            "bpm_anomaly": self.bpm_anomaly,
            "anomaly_type": self.anomaly_type,
            "avg_spo2": self.avg_spo2,
            "avg_bpm": self.avg_bpm,
            "window_seconds": self.window_seconds,
            "sample_count": self.sample_count,
        }


def _is_reading(s: Sample) -> bool:
    """Firmware returns 0 / 0.0 when no finger is on the sensor."""
    return s.bpm > 0 and s.spo2 > 0


def spo2_status(spo2: float) -> str:
    if spo2 <= 0:
        return "no_reading"
    if spo2 >= SPO2_NORMAL_LOW:
        return "normal"
    if spo2 >= SPO2_BORDERLINE_LOW:
        return "borderline"
    return "low"


def bpm_band(profile: Profile) -> tuple[int, int]:
    # Pediatric ranges (per onboarding modal reference table) take precedence
    # over the activity table because resting BPM differs sharply for children.
    if profile.age < 4:
        return 80, 130
    if profile.age < 12:
        return 75, 118
    row = BPM_TABLE.get(profile.activity, BPM_TABLE[ACTIVITY_DEFAULT])
    high = row["high_under_20"] if profile.age < 20 else row["high_20_plus"]
    return row["low"], high


def bpm_status(bpm: int, profile: Profile) -> str:
    if bpm <= 0:
        return "no_reading"
    low, high = bpm_band(profile)
    if bpm < low:
        return "low"
    if bpm > high:
        return "high"
    return "normal"


def _streak_seconds(samples: Sequence[Sample], predicate) -> float:
    """Length in seconds of the contiguous tail where every reading-bearing
    sample matches `predicate`. Zero-valued samples break the streak.
    """
    if not samples:
        return 0.0
    end_ts = samples[-1].ts
    streak_start = end_ts
    matched = False
    for s in reversed(samples):
        if not _is_reading(s):
            break
        if not predicate(s):
            break
        streak_start = s.ts
        matched = True
    return (end_ts - streak_start) if matched else 0.0


def _anomaly_label(spo2_anomaly: bool, bpm_anomaly: bool,
                   spo2_state: str, bpm_state: str) -> str:
    if spo2_anomaly and spo2_state == "low":
        return "spo2_low"
    if spo2_anomaly and spo2_state == "borderline":
        return "spo2_borderline"
    if bpm_anomaly and bpm_state == "low":
        return "bpm_low"
    if bpm_anomaly and bpm_state == "high":
        return "bpm_high"
    return "none"


def evaluate(samples: Sequence[Sample], profile: Profile, *,
             spo2_debounce_s: int, bpm_debounce_s: int) -> SessionVerdict:
    readings = [s for s in samples if _is_reading(s)]

    if not readings:
        window = 0
        if samples:
            window = int(samples[-1].ts - samples[0].ts)
        return SessionVerdict(
            spo2_status="no_reading",
            bpm_status="no_reading",
            spo2_anomaly=False,
            bpm_anomaly=False,
            anomaly_type="none",
            avg_spo2=None,
            avg_bpm=None,
            window_seconds=window,
            sample_count=len(samples),
        )

    avg_spo2 = sum(s.spo2 for s in readings) / len(readings)
    avg_bpm = sum(s.bpm for s in readings) / len(readings)

    latest = readings[-1]
    cur_spo2_state = spo2_status(latest.spo2)
    cur_bpm_state = bpm_status(latest.bpm, profile)

    spo2_streak = _streak_seconds(samples, lambda s: spo2_status(s.spo2) in ("borderline", "low"))
    bpm_streak = _streak_seconds(samples, lambda s: bpm_status(s.bpm, profile) in ("high", "low"))

    spo2_anomaly = spo2_streak >= spo2_debounce_s and cur_spo2_state in ("borderline", "low")
    bpm_anomaly = bpm_streak >= bpm_debounce_s and cur_bpm_state in ("high", "low")

    label = _anomaly_label(spo2_anomaly, bpm_anomaly, cur_spo2_state, cur_bpm_state)

    window = int(samples[-1].ts - samples[0].ts) if len(samples) > 1 else 0

    return SessionVerdict(
        spo2_status=cur_spo2_state,
        bpm_status=cur_bpm_state,
        spo2_anomaly=spo2_anomaly,
        bpm_anomaly=bpm_anomaly,
        anomaly_type=label,
        avg_spo2=round(avg_spo2, 1),
        avg_bpm=round(avg_bpm, 1),
        window_seconds=window,
        sample_count=len(samples),
    )


class RollingBuffer:
    """Time-bounded in-memory buffer of vitals samples.

    Single-process assumption: fine for the demo Flask dev server. A `Lock`
    guards `add`/`snapshot` so a future threaded WSGI worker stays safe.
    """

    def __init__(self, window_seconds: int) -> None:
        self._window = window_seconds
        self._buf: deque[Sample] = deque()
        self._lock = threading.Lock()

    def add(self, sample: Sample) -> None:
        with self._lock:
            self._buf.append(sample)
            cutoff = sample.ts - self._window
            while self._buf and self._buf[0].ts < cutoff:
                self._buf.popleft()

    def snapshot(self) -> list[Sample]:
        with self._lock:
            return list(self._buf)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()
