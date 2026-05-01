# Sleep & Cardiac Monitor with Kirby AI Diagnostics

A full-stack web app that monitors SpO2 and BPM from a LilyGO TTGO T-Display V1.1 wearable, evaluates readings against clinical thresholds, and delivers conversational wellness coaching with Anthropic Claude as a friendly virtual pet named Kirby.

## Project Lineage

This repo extends an existing Diploma in Biomedical Engineering capstone into a Flask + browser dashboard. The hardware firmware and Flutter reference app are treated as read-only specifications for the data contract.

Original capstone collaborators:
- BME Team: Andrea Rudd, Wong Xin Hui
- CEN Collaborators: Nabil Bin Mohamad Aszami, Muhamad Ikram Bin Dins Esfian, Phang Zhi Hao
- Supervisor: Raja Rangaswamy (TP)
- Industry Partner: Dr. Baey (SleepEasy Clinic)

## What Already Works

The T-Display firmware and Flutter reference client are already validated. Do not rewrite these unless explicitly asked.

T-Display firmware (`arduino_sketch/health_monitor/`):
- LilyGO TTGO T-Display V1.1
- Integrated 1.14-inch ST7789 TFT display
- MAX30102 PPG sensor for SpO2 and BPM via IR + Red light
- I2C pins for MAX30102: SDA 21, SCL 22
- MPU6050 6-axis IMU for movement and restlessness
- Core 0 drives the TFT and UI; Core 1 polls sensors and hosts an ESPAsyncWebServer
- Wi-Fi endpoint at `http://<ESP_IP>/data` returns JSON: `{bpm, spo2}`
- Firmware returns zeros when no finger is on the sensor
- WiFi credentials live in `arduino_sketch/health_monitor/secrets.h` (copy from `secrets.h.example`)

Flutter mobile app (reference only, see `flutter_code_for_project.txt`):
- Multi-profile support with age, activity level, exercise frequency
- Live IR and Red waveform plotting
- Session reporting and CSV export
- Local history with shared_preferences

Clinical validation against LePu commercial pulse oximeter:
- SpO2 deviation: approx ±2%
- BPM deviation: approx ±3 BPM

## What This Repo Builds

A Python Flask web app that:
1. Pulls live JSON from the T-Display over the local network
2. Plots BPM and SpO2 in the browser as live line charts with numeric readouts
3. Evaluates readings against medical thresholds and debounced anomaly rules
4. Triggers Kirby alerts via Anthropic Claude when an anomaly is detected
5. Speaks Kirby replies in the browser using the Web Speech API
6. Accepts both text and voice chat from the browser
7. Looks up nearby clinics via Google Places and can hand off booking links to Telegram for mobile booking

## Repository Structure

```
my_health_monitor_project/
├── arduino_sketch/
│   └── health_monitor/
│       ├── health_monitor.ino
│       ├── secrets.h.example
│       └── secrets.h (gitignored)
├── flask_web_app/
│   ├── app.py
│   ├── config.py
│   ├── diagnostics.py
│   ├── llm.py
│   ├── clinics.py
│   ├── telegram_bot.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── routes/
│   ├── static/
│   └── templates/
├── CLAUDE.md
├── CONTEXT.md
├── PLAN.md
└── README.md
```

## Build Phases

Phase 1: Real-time data ingestion. Flask serves the dashboard. JS polls `http://<ESP_IP>/data` and plots BPM and SpO2.

Phase 2: Threshold evaluation. Backend checks vitals against medical baselines. SpO2 below 95% for 30 seconds or resting BPM outside an age-and-activity adjusted band for 60 seconds triggers an anomaly flag. Movement-based restless detection is deferred (firmware does not currently emit `movement`).

Phase 3: Anthropic Haiku + Kirby + browser TTS. On anomaly, Kirby speaks a warm 1-2 sentence alert via the Web Speech API and the chat panel opens. The system prompt is seeded with the anomalous reading. Kirby asks one lifestyle question and gives personalised, non-prescriptive guidance.

## Tech Stack

- Hardware: LilyGO TTGO T-Display V1.1, MAX30102, MPU6050
- Firmware: Arduino C++ with TFT_eSPI, ESPAsyncWebServer
- Mobile reference: Flutter 3 with fl_chart
- Web backend: Python 3.11+, Flask, requests, python-dotenv, langchain-anthropic
- Frontend: vanilla JS, Chart.js, Web Speech API for TTS and voice input
- AI: Anthropic Claude `claude-haiku-4-5`

## Environment

Copy `.env.example` to `../.env` from `flask_web_app` and fill in real values. Never commit `.env`.

Required values:
- `ESP32_IP`
- `FLASK_SECRET_KEY`
- `ANTHROPIC_API_KEY`

Optional values:
- `GOOGLE_PLACES_API_KEY` for nearby clinic lookup
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for Telegram booking handoff

## Quickstart

```bash
cd flask_web_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example ..\.env
# edit ..\.env and fill in the required keys
flask --app app run --debug
```

Open `http://localhost:5000` and verify the dashboard.

## Notes on Clinic Search and Telegram Handoff

- `clinics.py` uses Google Places API (New) to look up nearby clinics, doctors, and hospitals.
- `llm.py` detects booking intent and can invoke `send_booking_to_telegram`.
- `telegram_bot.py` sends a Telegram card with inline buttons for Maps and website links.
- Booking handoff is intended for mobile use, since Singpass auth is smoother on a phone.

## Known Limitations

- The web app currently ingests only BPM and SpO2, not IMU or raw PPG values.
- The firmware returns zeros when no finger is on the sensor; the frontend skips those samples.
- The current system is for local network use only. No cloud database is enabled.
- The AI is wellness coaching only and not a medical diagnosis tool.

## License

To be added.
