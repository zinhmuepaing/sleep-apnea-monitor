# CONTEXT.md

Quick lookup for hardware specs, existing code, and clinical numbers. Keep this file updated as the project evolves.

## Hardware Summary

| Component       | Part            | Role                                          |
|-----------------|-----------------|-----------------------------------------------|
| Microcontroller | LilyGO TTGO T-Display V1.1 | Dual-core, built-in TFT, Wi-Fi          |
| Firmware path   | `arduino_sketch/health_monitor/` | Core 1 hosts Wi-Fi `/data`; Core 0 drives TFT |
| PPG sensor      | MAX30102        | SpO2 and BPM via IR + Red light; I2C SDA 21, SCL 22 |
| IMU             | MPU6050         | 6-axis accelerometer + gyro for movement      |
| Display         | Integrated 1.14-inch ST7789 TFT | Two-card dashboard: BPM (heart-ECG icon, beat-pulse dot, status strip) + SpO2 (droplet-O2 icon, status strip). Idle/splash screens use the same header bar. Display logic only — sensor math is locked. |
| Enclosure       | Black nylon, 3D printed | Blocks ambient light, USB charge port |
| Power           | LiPo + 3-pin slide switch | Portable                            |

## Firmware Behaviour Reference

Loop runs continuously in `arduino_sketch/health_monitor/health_monitor.ino`.
The firmware reads MAX30102 data, applies smoothing and beat detection, and hosts a local web endpoint.

Key payload behaviour:
- `GET /data` returns JSON with only `spo2` and `bpm`
- The web app ignores `movement`, `ir`, and `red` because the current firmware payload is scoped to BPM and SpO2
- `bpm` is int, 20-255; `0` means no finger on sensor
- `spo2` is float, 88.0-100.0; `0.0` means no finger on sensor

## Flutter App Behaviour Reference

The Flutter app is the canonical reference for threshold logic and profile modelling in the Flask app.

Profile model:
```json
{
  "name": "string",
  "age": 25,
  "activityLevel": "Sedentary | Lightly active | Moderately active | Very active",
  "exerciseFreq": "1×/week or less | 2–3×/week | 4–5×/week | Daily",
  "historySessions": []
}
```

Session record (one per second during recording):
```json
{
  "date": "YYYY-MM-DD",
  "time": "HH:MM:SS",
  "spo2": 97.3,
  "bpm": 72,
  "ir": 84210,
  "red": 65120,
  "movement": "No"
}
```

CSV export schema (Flutter, reference only): `Date, Time, SpO2, BPM, IR, RED, Movement`

Flask CSV export schema (Phase 4, current): `Timestamp, BPM, SpO2, BPM Level, SpO2 Level`. One row every 30 s of session uptime; rows where the sensor reported `0` (no finger) are skipped. Levels collapse `diagnostics` statuses to `Lower` / `Optimal` / `Higher` (SpO2 borderline maps to Lower).

History session snapshot (saved on Save to History):
```json
{
  "name": "...",
  "date": "...",
  "timeRange": "HH:MM - HH:MM",
  "duration": "X min Y sec",
  "csvPath": "...",
  "age": 25,
  "activityLevel": "...",
  "exerciseFreq": "...",
  "avgSpo2": 96.4,
  "avgBpm": 71,
  "restlessPct": 12.0,
  "spo2Msg": "...",
  "bpmMsg": "...",
  "moveMsg": "..."
}
```

The Flask app should use the same field names so clients stay aligned.

## Clinical Validation Numbers

Tested against a LePu commercial pulse oximeter:
- SpO2 deviation: approx ±2%
- BPM deviation: approx ±3 BPM

These figures matter for the chat prompt. The AI should never claim higher precision than the sensor delivers.

## Acceptable Use Statement

This is consumer-grade home wellness monitoring. It is not a substitute for clinical-grade SpO2, ECG, or polysomnography. Every AI response must end with a clinician-referral cue when symptoms persist.

## Reference Repo

Flask routing and LLM call style: `https://github.com/zinhmuepaing/Career-Quest-Map.git`

## Glossary

- OSA: Obstructive Sleep Apnea
- AFib: Atrial Fibrillation
- PPG: Photoplethysmography
- SpO2: Peripheral capillary oxygen saturation
- BPM: Beats per minute
- HRV: Heart rate variability (future scope)
- SMA: Simple moving average
- IMU: Inertial measurement unit

## Service Integration Notes

The Flask app now includes clinic lookup and Telegram handoff.

- `clinics.py` calls `places:searchText` (primary, accepts natural-language queries like "clinics in Singapore") with a `places:searchNearby` distance fallback. Reads `GOOGLE_PLACES_API_KEY` lazily; degrades to `[]` on any error.
- `llm.py` binds a `send_booking_to_telegram` Anthropic tool. Kirby decides when to call it; the dispatcher in `_invoke` runs the tool and feeds the result back through one tool-use round trip.
- `telegram_bot.py` is bidirectional: outbound `send_booking_card` (refactored through a shared `send_message`) plus optional inbound long-polling started by `app.py`.
- `routes/debug.py` exposes `GET /api/clinics/test` for validating the Places API key, billing, and request shape.

Env vars:
- `GOOGLE_PLACES_API_KEY`: enables nearby clinic lookup. Requires "Places API (New)" enabled on the Google Cloud project (legacy "Places API" is a separate product).
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from @BotFather
- `TELEGRAM_CHAT_ID`: tester's personal Telegram chat id (booking-card destination)
- `TELEGRAM_POLLING_ENABLED`: `true` to start the inbound polling thread on boot. Default off.


## Telegram as a Second Surface

The bot @medicalAppointmentBookingBot now does two things:

1. **Push** (Phase 5): one-way booking card, sent by Kirby's tool call from either surface.
2. **Read** (Phase 6): Telegram users tap buttons or send messages. Flask polls Telegram on a daemon thread.

Inbound is opt-in via `TELEGRAM_POLLING_ENABLED=true` in `.env`. Only one running instance should poll at a time per bot token (Telegram delivers each update to only one getUpdates caller).

Kirby chat ids on Telegram are namespaced as `f"tg-{telegram_chat_id}"`, kept separate from the web's per-tab chat ids. Conversation memory still lives in the same in-process dict in `llm.py`.

Vitals on Telegram come from the same `RollingBuffer` and `evaluate()` the dashboard uses; no duplicate state.
