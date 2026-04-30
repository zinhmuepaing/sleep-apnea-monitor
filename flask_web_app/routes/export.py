"""Session CSV export.

Maintains an unbounded, in-memory log of every vitals sample seen this run
(the rolling buffer in `verdict.py` is time-bounded and unsuitable for export).
`record_sample` is called from the verdict poll path; `GET /api/export.csv`
streams the log as a five-column CSV per the Phase 4 spec.

Columns: Timestamp, BPM, SpO2, BPM Level, SpO2 Level.
Levels collapse `diagnostics` statuses to Lower / Optimal / Higher.
No-finger samples (bpm=0 or spo2=0) are excluded.
"""

from __future__ import annotations

import csv
import io
import threading
from datetime import datetime

from flask import Blueprint, Response

from diagnostics import Sample, bpm_status, spo2_status
from routes._profile import get_profile

bp = Blueprint("export", __name__, url_prefix="/api")

# Log one sample every 30 seconds. The dashboard polls at 1 Hz; logging at the
# poll cadence makes the CSV unwieldy. Verdict logic still sees every poll.
LOG_INTERVAL_SECONDS = 30.0

_session_log: list[Sample] = []
_last_logged_ts: float = 0.0
_lock = threading.Lock()


def record_sample(sample: Sample) -> None:
    global _last_logged_ts
    with _lock:
        if sample.ts - _last_logged_ts < LOG_INTERVAL_SECONDS:
            return
        _session_log.append(sample)
        _last_logged_ts = sample.ts


def _snapshot() -> list[Sample]:
    with _lock:
        return list(_session_log)


_BPM_LEVEL = {"low": "Lower", "normal": "Optimal", "high": "Higher"}
_SPO2_LEVEL = {"low": "Lower", "borderline": "Lower", "normal": "Optimal"}


@bp.get("/export.csv")
def export_csv():
    profile = get_profile()
    samples = _snapshot()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Timestamp", "BPM", "SpO2", "BPM Level", "SpO2 Level"])

    for s in samples:
        if s.bpm <= 0 or s.spo2 <= 0:
            continue
        ts = datetime.fromtimestamp(s.ts).strftime("%Y-%m-%d %H:%M:%S")
        bpm_lvl = _BPM_LEVEL.get(bpm_status(s.bpm, profile), "Optimal")
        spo2_lvl = _SPO2_LEVEL.get(spo2_status(s.spo2), "Optimal")
        writer.writerow([ts, s.bpm, f"{s.spo2:.1f}", bpm_lvl, spo2_lvl])

    filename = f"health_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
