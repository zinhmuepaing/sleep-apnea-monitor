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

## Phase 1: Real-Time Data Ingestion [DONE]

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

## Phase 4: Polishing and Safety [DONE]

Goal: the app is demo-ready and robust to bad input.

Tasks:
- Session CSV export with a 30-second sample throttle. 5 columns: `Timestamp, BPM, SpO2, BPM Level, SpO2 Level`. Levels collapse to `Lower` / `Optimal` / `Higher`. No-finger rows skipped.
- Profile defaults (sedentary, age 30) wired through `routes/_profile.py`; full entry screen deferred.
- Google Places API (New) clinic lookup via `clinics.py` with Text Search primary and Nearby Search fallback. Debug endpoint `GET /api/clinics/test`.
- T-Display disconnect surfaces as a status pill error; the chart pauses cleanly.
- Input sanitisation on `/api/chat/message` (length cap, JSON-only response on error).
- Frontend UI refresh: orb-pill "Ask Kirby" trigger, glass-morphism chat panel, Kirby + user avatars, lucide-style mic, asymmetric bubbles.

Exit criterion: download the CSV mid-session and confirm the schema; ask Kirby to find clinics in Singapore and verify Places returns real polyclinics; pull the T-Display plug and watch the dashboard recover.

## Phase 5: Telegram Mobile Handoff for Booking [DONE]

Goal: when the user asks to book a clinic appointment, push a Telegram card with inline buttons to their phone so they can authenticate via Singpass on mobile.

Backend:
- `flask_web_app/telegram_bot.py::send_booking_card(clinic_name, maps_url="", website_url="")` reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` at call time. Card has two URL buttons: "📍 View on Maps" and "🏥 Visit Clinic Website" (Maps-only when no website).
- `llm.py` exposes a Claude tool `send_booking_to_telegram(clinic_name, maps_url, website_url)`. Kirby calls it; `_invoke` dispatches one tool-use round trip and feeds the result back as a `ToolMessage`.
- Bot identity: `@medicalAppointmentBookingBot`, persona Kirby (same identity as the web chat).

Frontend:
- No changes. Kirby's text reply tells the user to check their phone. Web Speech speaks it aloud.

Exit criterion: in chat, after Kirby has listed clinics, type "book me at <name>". Within 2 seconds the tester's phone receives a Telegram card with the two working buttons. The web chat shows Kirby's "You chose ..." confirmation.

## Phase 6: Telegram Bot as a Second Surface [DONE]

Goal: the user can open @medicalAppointmentBookingBot, tap My Vitals to see live BPM and SpO2 with a chart, or tap Chat with Kirby to ask anything they would ask on the web. Booking still pushes the existing card with View on Maps and Visit Clinic Website buttons.

Backend:
- `telegram_bot.py` grows from one push function into a small module: outbound primitives, a vitals snapshot builder (text + matplotlib chart PNG), and an inbound long-polling loop started by `app.py` at boot.
- `llm.py` adds `continue_chat_for_telegram` that calls the same Kirby logic without a lat/lon and prompts the user to share their location through Telegram's attachment if a clinic search is requested.
- The web app is untouched. No route changes. No template changes.

Frontend (the bot):
- A persistent reply keyboard with three labelled buttons: 💓 My Vitals, 🐾 Chat with Kirby, 💡 Help.
- `/start`, `/help`, `/status`, `/menu` commands.
- The existing booking card (Phase 5) is the booking output for both web and Telegram.
- `TELEGRAM_EMOJI_DIRECTIVE` injects a per-turn instruction telling Kirby to use 1-3 contextually relevant emojis on Telegram only; the web app stays emoji-free.

Exit criterion: with `TELEGRAM_POLLING_ENABLED=true`, send `/start` to the bot. The keyboard appears. Tap 💓 My Vitals: a chart and current readings appear. Tap 🐾 Chat with Kirby, ask wellness questions, ask for clinics, then "book the first one", the booking card arrives in the same chat.

## Phase 7: User Onboarding Modal [DONE]

Goal: capture Name, Age, and Activity Level on first page load so thresholds and CSV filenames are personalised from the first sample.

Backend:
- `routes/profile.py` blueprint: `GET /api/profile` returns `{ok, set, profile}` so the frontend can skip the modal if the session already has a profile. `POST /api/profile` validates `{name, age, activity}` and writes to `flask.session["profile"]`. Persists for the lifetime of the browser session cookie.
- `diagnostics.py` `Profile` dataclass gains a `name` field (default `"user"`). `bpm_band()` now branches on age first: ages 0-3 use 80-130 BPM; ages 4-11 use 75-118 BPM; ages 12+ continue to use the activity-aware `BPM_TABLE`.
- `routes/_profile.py` reads `name` from session and adds it to the `Profile` object.
- `routes/export.py` CSV filename changes from `health_session_<timestamp>.csv` to `health_<name>_age<age>_<timestamp>.csv`.

Frontend:
- `templates/index.html` renders the modal as the first element of `<body>`. Body opens with class `modal-open` to blur the dashboard from first paint, eliminating any flash of unblurred content.
- Modal shows a reference table (four age-band rows) and three fields: Name, Age, Activity Level (dropdown).
- Save Changes button is disabled until all three fields contain valid data (name 1-60 chars, age integer 1-120, activity selected).
- No close button, no Escape key, no backdrop click. The dashboard is inaccessible until the form is submitted.
- On success, the modal hides and the poll loop starts.
- On refresh, `GET /api/profile` runs first: if the session cookie is still valid, the modal is skipped and polling starts immediately.

Exit criterion: open the app in a fresh incognito tab, the modal appears, dashboard is blurred. Fill in all fields; Save enables. Click Save; modal closes and live vitals begin. Refresh; modal does not reappear. Download CSV; filename includes name and age. Set age to 2; verify `/api/verdict` reports a BPM band of 80-130.

## Phase 8: Deferred

Out of scope for this build, revisit after partner feedback:
- Cloud database for long-term history
- Multi-user authentication and per-user `TELEGRAM_CHAT_ID` resolution
- Direct T-Display to cloud upload (firmware change)
- Real-time PPG analysis on the backend (FFT, HRV, irregularity detection)
- ECG sensor integration (blocked by T-Display memory)
- Movement-based restless detection (requires firmware to re-emit `movement`)
- Capturing `update["message"]["location"]` so Kirby can do clinic search from a Telegram-shared location
