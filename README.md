# Sleep & Cardiac Monitor with Kirby AI Diagnostics

A full-stack IoT and AI application that detects and helps manage Obstructive Sleep Apnea (OSA) and Atrial Fibrillation. The system reads SpO2 and heart rate (BPM) from a LilyGO TTGO T-Display V1.1 wearable, streams it to a Flask web dashboard, and uses Anthropic Claude (model `claude-haiku-4-5` via `langchain-anthropic`) to deliver conversational health coaching, voiced by a warm virtual pet named Kirby, when readings fall outside safe thresholds.

## Project Lineage

This web platform is the next evolution of an existing Diploma in Biomedical Engineering capstone. The hardware and Flutter app already exist and are clinically validated. The Flask + Anthropic Claude (Kirby) layer is the new component being built in this repository.

Original capstone collaborators:
- BME Team: Andrea Rudd, Wong Xin Hui
- CEN Collaborators: Nabil Bin Mohamad Aszami, Muhamad Ikram Bin Dins Esfian, Phang Zhi Hao
- Supervisor: Raja Rangaswamy (TP)
- Industry Partner: Dr. Baey (SleepEasy Clinic)

## What Already Works

The T-Display firmware and Flutter app are production-tested. Do not rewrite these unless explicitly asked.

T-Display firmware (`esp32_firmware/`):
- LilyGO TTGO T-Display V1.1, dual-core
- Integrated 1.14-inch ST7789 TFT display
- MAX30102 PPG sensor for SpO2 and BPM via IR and Red light
- I2C pins for MAX30102: SDA 21, SCL 22
- MPU6050 6-axis IMU for movement and restlessness
- Core 0 drives the integrated 1.14-inch ST7789 TFT display and live PPG plot
- Core 1 polls sensors, applies SMA and median filters, hosts an ESPAsyncWebServer
- PlatformIO environment target: `lilygo-t-display`
- Wi-Fi endpoint at `http://<ESP_IP>/data` returns JSON: `{bpm, spo2}` (returns zeros when no finger is on the sensor)
- WiFi credentials live in `arduino_sketch/health_monitor/secrets.h` (copy from `secrets.h.example`)

Flutter mobile app (reference only, see `flutter_code_for_project.txt`):
- Multi-profile support with age, activity level, exercise frequency
- Live IR and Red waveform plotting
- Session reporting and CSV export
- Local history with shared_preferences

Clinical validation against LePu commercial oximeter:
- SpO2 deviation: approx ±2%
- BPM deviation: approx ±3 BPM

## What This Repo Builds

A Python Flask web application that:
1. Pulls live JSON from the T-Display over the local network
2. Plots BPM and SpO2 in the browser as live line charts with numeric readouts
3. Evaluates readings against medical thresholds (BPM + SpO2 only; movement deferred until firmware revision)
4. Triggers an Anthropic Claude chat session, voiced as Kirby, when anomalies are detected
5. Speaks Kirby's alerts in the browser via the Web Speech API
6. Accepts voice replies via the browser microphone (Web Speech `SpeechRecognition`) with auto-send when the user stops speaking
7. Asks the user diagnostic questions and produces personalised, medically safe lifestyle suggestions

## Repository Structure

```
my_health_monitor_project/
├── esp32_firmware/            # PlatformIO C++ project (existing, do not modify without asking)
│   ├── src/main.cpp
│   └── platformio.ini
├── flask_web_app/             # NEW: Python Flask backend
│   ├── static/                # JS for fetch + live graphing, CSS
│   ├── templates/             # index.html (dashboard + chat UI)
│   ├── app.py                 # App factory, blueprint registration
│   ├── diagnostics.py         # Threshold logic + rolling buffer
│   ├── llm.py                 # Anthropic ChatAnthropic wrapper (Kirby persona)
│   ├── config.py              # Env loading, threshold constants
│   ├── requirements.txt
│   └── .env.example
├── docs/
│   └── PROJECT_REPORT.pdf     # Original BME capstone report
├── CLAUDE.md                  # Project context for Claude Code
├── PLAN.md                    # Phased build plan
└── README.md
```

## Build Phases

Phase 1: Real-time data ingestion. Flask serves the dashboard. JS polls `http://<ESP_IP>/data` and plots SpO2, BPM, IR, Red live.

Phase 2: Threshold evaluation. Backend checks vitals against medical baselines. SpO2 below 95% for 30 seconds or resting BPM outside an age-and-activity adjusted band for 60 seconds triggers an anomaly flag. Movement-based restless detection is deferred (firmware does not currently emit `movement`).

Phase 3: Anthropic Haiku + Kirby + browser TTS. On anomaly, Kirby speaks a warm 1-2 sentence alert via the Web Speech API and the chat panel opens. The system prompt is seeded with the anomalous reading. Kirby asks one lifestyle question (alcohol, caffeine, sleep posture, recent activity) and returns personalised, non-prescriptive guidance.

## Tech Stack

- Hardware: LilyGO TTGO T-Display V1.1, MAX30102, MPU6050
- Firmware: Arduino C++ with TFT_eSPI, ESPAsyncWebServer
- Mobile reference: Flutter 3 with fl_chart
- Web backend: Python 3.11+, Flask, requests, python-dotenv, langchain-anthropic
- Frontend: vanilla JS, Chart.js, Web Speech API for both Kirby TTS and voice input
- AI: Anthropic Claude `claude-haiku-4-5`

## Quickstart

```bash
cd flask_web_app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in ANTHROPIC_API_KEY and ESP32_IP
flask --app app run --debug
```

Open `http://localhost:5000` and enter the T-Display IP if not preconfigured.

## Reference Repository

For Flask routing patterns and LLM call structure, mirror the conventions used in `https://github.com/zinhmuepaing/Career-Quest-Map.git`.

## Known Limitations Inherited from Hardware

- Current enclosure requires finger contact directly on the main unit. Wrist-worn redesign is on the roadmap.
- Manual CSV upload was the previous data path. This project replaces it with live streaming.
- ECG was dropped from the BME design due to T-Display memory limits. Future hardware may add it.
- PPG readings take a few seconds to stabilise after finger placement.

## License

To be added.
