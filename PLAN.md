# PLAN.md

Phased build plan. Do not skip phases. Each phase has an exit criterion. Stop and demo before moving on.

## Phase 0: Project Skeleton

Goal: a runnable empty Flask app that loads `.env` and serves a placeholder dashboard.

Deliverables:
- `flask_web_app/app.py` with one route `/` returning `index.html`
- `flask_web_app/config.py` loading env vars
- `flask_web_app/.env.example`
- `flask_web_app/requirements.txt`
- `flask_web_app/templates/index.html` placeholder
- `flask_web_app/static/css/main.css` placeholder

Exit criterion: `flask --app app run --debug` opens a page that says "Health Monitor Dashboard".

## Phase 1: Real-Time Data Ingestion

Goal: live vitals visible in the browser.

Backend:
- `GET /api/vitals` proxies the T-Display `http://<ESP_IP>/data`. Adds error handling for timeout, connection refused, and bad JSON. Returns `{"ok": true, "data": {...}}` or `{"ok": false, "error": "..."}`.
- Configurable polling target IP from `.env` with a fallback override via query string for testing.

Frontend:
- `static/js/dashboard.js` polls `/api/vitals` every 1 second
- Plots SpO2 and BPM as time-series line charts with numeric readouts
- Shows a status pill: connected, polling, no finger, or error

Exit criterion: with the T-Display powered and a finger on the sensor, the dashboard shows live SpO2 and BPM numbers and curves.

Note: PPG raw `ir` / `red` plotting and `movement` were dropped from the firmware payload to keep this dashboard lean. Phase 2 evaluates BPM and SpO2 only; restless detection is deferred until a firmware revision.

## Phase 2: Threshold Evaluation [DONE]

Goal: the backend flags anomalies.

Backend:
- `flask_web_app/diagnostics.py` with pure functions:
  - `bpm_band(profile) -> (low, high)`
  - `spo2_status(spo2) -> "normal" | "borderline" | "low" | "no_reading"`
  - `bpm_status(bpm, profile) -> "normal" | "high" | "low" | "no_reading"`
  - `evaluate(samples, profile, *, spo2_debounce_s, bpm_debounce_s) -> SessionVerdict`
- `RollingBuffer` of the last N samples in memory (default 5 minutes at 1 Hz = 300 samples), thread-safe.
- `GET /api/verdict` fetches the device, appends a sample, and returns the current rolling verdict.
- Anomaly debouncing: SpO2 borderline/low for 30s, BPM out of band for 60s. Movement-based restless detection is deferred.
- Single anomaly label, prioritised: `spo2_low` > `spo2_borderline` > `bpm_low` > `bpm_high` > `none`.

Frontend:
- A diagnostic card under the live charts showing current SpO2 status, BPM status, and rolling averages.
- A coloured anomaly banner that appears when an anomaly fires.

Exit criterion: holding your breath drops SpO2, the verdict goes Borderline within 30 seconds, the banner appears.

## Phase 3: Anthropic Haiku + Kirby + Web Speech I/O [DONE]

Goal: when an anomaly fires, Kirby speaks a warm 1-2 sentence alert and a chat panel opens for the user to reply by typing or by voice.

Backend:
- `flask_web_app/llm.py` wraps `ChatAnthropic` (`langchain-anthropic`) using model `claude-haiku-4-5` (snapshot `claude-haiku-4-5-20251001`). Builds the Kirby system prompt from the verdict + profile.
- `POST /api/chat/alert` body `{verdict, profile}`. Creates a new `chat_id`, returns Kirby's 1-2 sentence opener with one lifestyle question.
- `POST /api/chat/start` manual entry when there is no anomaly. Returns a friendly Kirby greeting.
- `POST /api/chat/message` body `{text, chat_id}`. Validates non-empty + length cap. Appends to memory, returns the next Kirby reply.
- Conversation history lives in a server-side dict keyed by `chat_id`. `chat_id` lives in `flask.session`. No DB.

Frontend:
- A slide-in chat panel triggered by the anomaly banner.
- Standard chat bubbles, send on Enter, scroll to bottom on new message.
- A persistent disclaimer at the top: "This is wellness coaching, not medical advice."
- Kirby replies are spoken via `window.speechSynthesis` (Web Speech API). No server-side audio.
- Voice input via `webkitSpeechRecognition`: a mic button populates the chat input with interim transcripts as the user speaks, then auto-submits the form when speech ends. Clicking the mic mid-recording cancels without sending. Hidden on browsers without Web Speech (Firefox).
- Anomaly transitions auto-trigger `/api/chat/alert`; repeats are suppressed while the same anomaly type stays active.

Exit criterion: trigger an SpO2 anomaly, Kirby speaks a warm question, the chat opens, the user replies, Kirby gives a safe suggestion ending with the clinician recommendation.

## Phase 4: Polishing and Safety

Goal: the app is demo-ready and robust to bad input.

Tasks:
- T-Display disconnection handling. Show a clear "device offline" state instead of crashing the chart.
- Profile entry screen so the user can set age, activity, and exercise frequency. Persist to a local JSON file.
- Session log download as CSV (mirror the schema from the Flutter app).
- Rate limiting on `/api/chat/message` to avoid runaway token spend.
- Input sanitisation on chat messages before sending to Anthropic.
- Loading states and error toasts.

Exit criterion: pull the T-Display plug mid-session, the dashboard recovers cleanly when it returns. Submit empty or huge chat messages, the backend rejects them with a friendly error.

## Phase 5: Deferred

Items that are out of scope for the first build:
- Cloud database for long-term history
- Multi-user authentication
- Direct T-Display to cloud upload (firmware change)
- Real-time PPG analysis on the backend (FFT, HRV, irregularity detection)
- ECG sensor integration (blocked by T-Display memory)

Revisit after Phase 4 ships and the supervisor and industry partner have given feedback.


## Phase 5: Telegram Mobile Handoff for Booking

Goal: when the user asks to book a clinic appointment, push a Telegram card with inline buttons to their phone so they can authenticate via Singpass on mobile.

Backend:
- `flask_web_app/telegram_bot.py` exposes `send_booking_card(name, maps_url, address)`. Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` at call time.
- `llm.py` adds `_is_booking_query` and `_extract_clinic_from_history`. `continue_chat` fires `send_booking_card` on a background thread and seeds Kirby's reply with a handoff prompt.
- Bot identity: @medicalAppointmentBookingBot, registered as Kirby with @BotFather.
- For MVP, `TELEGRAM_CHAT_ID` is hardcoded for one tester. Multi-user linking is deferred.

Frontend:
- No changes. Kirby's text reply tells the user to check their phone. Web Speech speaks it aloud.

Exit criterion: in chat, after Kirby has listed clinics, type "book me an appointment at <clinic name>". Within 2 seconds the tester's phone receives a Telegram card with two working buttons. The web chat shows Kirby's handoff acknowledgment.
