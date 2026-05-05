"use strict";

const POLL_MS = parseInt(document.body.dataset.pollMs, 10) || 1000;
const SERIES_LEN = 120;        // ~2 minutes of vitals at 1 Hz

const pillEl = document.getElementById("status-pill");
const detailEl = document.getElementById("status-detail");
const spo2NowEl = document.getElementById("spo2-now");
const bpmNowEl = document.getElementById("bpm-now");

const verdictSpo2El = document.getElementById("verdict-spo2");
const verdictBpmEl = document.getElementById("verdict-bpm");
const verdictAvgSpo2El = document.getElementById("verdict-avg-spo2");
const verdictAvgBpmEl = document.getElementById("verdict-avg-bpm");
const verdictWindowEl = document.getElementById("verdict-window");
const verdictAnomalyEl = document.getElementById("verdict-anomaly");

const bannerEl = document.getElementById("anomaly-banner");
const bannerTextEl = document.getElementById("anomaly-banner-text");
const bannerOpenChatBtn = document.getElementById("anomaly-open-chat");

const chatPanelEl = document.getElementById("chat-panel");
const chatLogEl = document.getElementById("chat-log");
const chatFormEl = document.getElementById("chat-form");
const chatInputEl = document.getElementById("chat-input");
const chatToggleBtn = document.getElementById("chat-toggle");
const chatCloseBtn = document.getElementById("chat-close");

let lastAnomalyType = "none";
let lastVerdict = null;
let lastProfile = null;
let userCoords = null;        // { lat, lon } once geolocation succeeds
let geoInFlight = null;       // Promise of an in-progress permission request

const LOCATION_KEYWORDS = ["clinic", "doctor", "hospital", "nearest", "nearby", "near me", "around me"];

function isLocationIntent(text) {
  const t = text.toLowerCase();
  return LOCATION_KEYWORDS.some((kw) => t.includes(kw));
}

// Request geolocation. Returns a Promise that resolves to coords or null.
// Re-asks on every call where coords are missing, so the user can grant
// permission later (e.g. they declined the first prompt, then asked Kirby
// for clinics and the app re-prompts at that moment).
function requestGeolocation() {
  if (userCoords) return Promise.resolve(userCoords);
  if (geoInFlight) return geoInFlight;
  if (!("geolocation" in navigator)) return Promise.resolve(null);

  geoInFlight = new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        userCoords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        resolve(userCoords);
      },
      () => { resolve(null); },   // declined or unavailable
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 5 * 60 * 1000 }
    );
  }).finally(() => { geoInFlight = null; });

  return geoInFlight;
}

function setStatus(state, detail = "") {
  pillEl.className = `pill pill-${state}`;
  pillEl.textContent = state;
  detailEl.textContent = detail;
}

function setPill(el, state, text) {
  el.className = `pill pill-${state}`;
  el.textContent = text;
}

const baseLineOpts = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
  scales: {
    x: {
      ticks: { color: "#64748b", maxTicksLimit: 6, font: { size: 10 } },
      grid: { color: "rgba(15, 23, 42, 0.06)" },
      border: { color: "rgba(15, 23, 42, 0.1)" },
    },
    y: {
      ticks: { color: "#64748b", font: { size: 10 } },
      grid: { color: "rgba(15, 23, 42, 0.06)" },
      border: { color: "rgba(15, 23, 42, 0.1)" },
    },
  },
  elements: { point: { radius: 0 }, line: { tension: 0.3, borderWidth: 2 } },
};

const spo2Chart = new Chart(document.getElementById("chart-spo2"), {
  type: "line",
  data: {
    labels: [],
    datasets: [{
      data: [],
      borderColor: "#10b981",
      backgroundColor: "rgba(16, 185, 129, 0.12)",
      fill: true,
    }],
  },
  options: { ...baseLineOpts, scales: { ...baseLineOpts.scales, y: { ...baseLineOpts.scales.y, suggestedMin: 85, suggestedMax: 100 } } },
});

const bpmChart = new Chart(document.getElementById("chart-bpm"), {
  type: "line",
  data: {
    labels: [],
    datasets: [{
      data: [],
      borderColor: "#ec4899",
      backgroundColor: "rgba(236, 72, 153, 0.12)",
      fill: true,
    }],
  },
  options: { ...baseLineOpts, scales: { ...baseLineOpts.scales, y: { ...baseLineOpts.scales.y, suggestedMin: 40, suggestedMax: 130 } } },
});

function pushPoint(chart, label, value, cap) {
  const ds = chart.data.datasets[0];
  chart.data.labels.push(label);
  ds.data.push(value);
  if (chart.data.labels.length > cap) {
    chart.data.labels.shift();
    ds.data.shift();
  }
  chart.update("none");
}

function speak(text) {
  if (!("speechSynthesis" in window) || !text) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1.0;
  u.pitch = 1.2;   // playful Kirby
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

const KIRBY_AVATAR_SRC = document.body.dataset.kirbyAvatar || "";
const USER_AVATAR_SRC = document.body.dataset.userAvatar || "";

function buildAvatarEl(role) {
  const span = document.createElement("span");
  span.className = "msg-avatar";
  const src = role === "user" ? USER_AVATAR_SRC : KIRBY_AVATAR_SRC;
  const alt = role === "user" ? "You" : "Kirby";
  if (src) {
    const img = document.createElement("img");
    img.src = src;
    img.alt = alt;
    img.width = 32;
    img.height = 32;
    span.appendChild(img);
  } else {
    span.textContent = role === "user" ? "🙂" : "🐾";
  }
  return span;
}

function buildMessageRow(role) {
  const row = document.createElement("div");
  row.className = `msg msg-${role}`;
  row.appendChild(buildAvatarEl(role));
  const body = document.createElement("div");
  body.className = "msg-body";
  if (role !== "user") {
    const name = document.createElement("span");
    name.className = "msg-name";
    name.textContent = role === "error" ? "Kirby" : "Kirby";
    body.appendChild(name);
  }
  row.appendChild(body);
  return { row, body };
}

function appendBubble(role, text) {
  const { row, body } = buildMessageRow(role);
  const bubble = document.createElement("div");
  bubble.className = `bubble bubble-${role}`;
  bubble.textContent = text;
  body.appendChild(bubble);
  chatLogEl.appendChild(row);
  chatLogEl.scrollTop = chatLogEl.scrollHeight;
}

function openChat() {
  chatPanelEl.classList.remove("chat-hidden");
  chatInputEl.focus();
  requestGeolocation();
}

function appendLinksBubble(links) {
  if (!Array.isArray(links) || links.length === 0) return;
  const { row, body } = buildMessageRow("kirby");
  const div = document.createElement("div");
  div.className = "bubble bubble-kirby bubble-links";
  const list = document.createElement("ul");
  list.className = "link-list";
  for (const c of links) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = c.maps_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    const km = (c.distance_m / 1000).toFixed(1);
    a.textContent = `${c.name} — ${km} km`;
    li.appendChild(a);
    if (c.address) {
      const addr = document.createElement("div");
      addr.className = "link-addr";
      addr.textContent = c.address;
      li.appendChild(addr);
    }
    if (c.website) {
      li.appendChild(document.createTextNode(" · "));
      const w = document.createElement("a");
      w.href = c.website;
      w.target = "_blank";
      w.rel = "noopener noreferrer";
      w.textContent = "website";
      li.appendChild(w);
    }
    list.appendChild(li);
  }
  div.appendChild(list);
  body.appendChild(div);
  chatLogEl.appendChild(row);
  chatLogEl.scrollTop = chatLogEl.scrollHeight;
}

function closeChat() {
  chatPanelEl.classList.add("chat-hidden");
}

bannerOpenChatBtn.addEventListener("click", openChat);
chatToggleBtn.addEventListener("click", openChat);
chatCloseBtn.addEventListener("click", closeChat);

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const ctype = res.headers.get("content-type") || "";
  if (!ctype.includes("application/json")) {
    const snippet = (await res.text()).slice(0, 120).replace(/\s+/g, " ");
    throw new Error(`server returned non-JSON (HTTP ${res.status}): ${snippet}`);
  }
  return res.json();
}

chatFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = chatInputEl.value.trim();
  if (!text) return;
  appendBubble("user", text);
  chatInputEl.value = "";
  try {
    const payload = { text };

    // If the user is asking about a location and we don't have coords yet,
    // prompt the browser now. Surface a friendly nudge if they decline.
    if (isLocationIntent(text) && !userCoords) {
      appendBubble("kirby", "I need your location to find nearby clinics. Please allow location access in your browser when prompted.");
      const coords = await requestGeolocation();
      if (!coords) {
        appendBubble("error", "Location is blocked. Enable it in the browser's site settings, then ask me again.");
        return;
      }
    }

    if (userCoords) { payload.lat = userCoords.lat; payload.lon = userCoords.lon; }
    const body = await postJson("/api/chat/message", payload);
    if (body.ok) {
      appendBubble("kirby", body.text);
      speak(body.text);
      if (body.links && body.links.length) appendLinksBubble(body.links);
    } else {
      appendBubble("error", body.error || "Kirby is quiet right now.");
    }
  } catch (err) {
    appendBubble("error", err.message || "network error");
  }
});

async function fireKirbyAlert(verdict, profile) {
  try {
    const body = await postJson("/api/chat/alert", { verdict, profile });
    if (body.ok) {
      appendBubble("kirby", body.text);
      speak(body.text);
      openChat();
    } else {
      // No-key fallback or LLM error: keep the banner, do not speak.
      appendBubble("error", `Kirby unavailable: ${body.error}`);
    }
  } catch (err) {
    appendBubble("error", err.message || "network error");
  }
}

function renderVerdict(verdict) {
  setPill(verdictSpo2El, verdict.spo2_status, verdict.spo2_status);
  setPill(verdictBpmEl, verdict.bpm_status, verdict.bpm_status);
  verdictAvgSpo2El.textContent = verdict.avg_spo2 != null ? `${verdict.avg_spo2}%` : "--";
  verdictAvgBpmEl.textContent = verdict.avg_bpm != null ? verdict.avg_bpm : "--";
  verdictWindowEl.textContent = `${verdict.window_seconds}s (${verdict.sample_count})`;
  setPill(verdictAnomalyEl, verdict.anomaly_type, verdict.anomaly_type);

  const fired = verdict.anomaly_type !== "none";
  if (fired) {
    bannerEl.classList.remove("banner-hidden");
    bannerTextEl.textContent = `Anomaly: ${verdict.anomaly_type.replace("_", " ")}.`;
  } else {
    bannerEl.classList.add("banner-hidden");
  }
}

async function pollLoop() {
  setStatus("polling");
  try {
    const res = await fetch("/api/verdict", { cache: "no-store" });
    const body = await res.json();

    if (!body.ok) {
      setStatus("error", body.error || "unknown error");
      return;
    }

    const { verdict, profile, latest } = body;
    lastVerdict = verdict;
    lastProfile = profile;

    const t = new Date().toLocaleTimeString();
    const hasReading = Number(latest.bpm) > 0 && Number(latest.spo2) > 0;

    if (hasReading) {
      spo2NowEl.textContent = Number(latest.spo2).toFixed(1);
      bpmNowEl.textContent = latest.bpm;
      pushPoint(spo2Chart, t, latest.spo2, SERIES_LEN);
      pushPoint(bpmChart, t, latest.bpm, SERIES_LEN);
      setStatus("connected", `last ${t}`);
    } else {
      spo2NowEl.textContent = "--";
      bpmNowEl.textContent = "--";
      setStatus("connected", "no finger");
    }

    renderVerdict(verdict);

    // Auto-trigger Kirby on first transition into a new anomaly type. Suppress
    // while the same type stays active.
    if (verdict.anomaly_type !== "none" && verdict.anomaly_type !== lastAnomalyType) {
      fireKirbyAlert(verdict, profile);
    }
    lastAnomalyType = verdict.anomaly_type;
  } catch (e) {
    setStatus("error", e.message || "fetch failed");
  }
}

function setupVoiceInput() {
  const micBtn = document.getElementById("chat-mic");
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!Rec) {
    micBtn.classList.add("is-hidden");
    return;
  }

  const recognition = new Rec();
  recognition.lang = "en-US";
  recognition.interimResults = true;   // live feedback as the user speaks
  recognition.continuous = false;
  recognition.maxAlternatives = 1;

  let recording = false;
  let voicePrefix = "";   // text the user had typed before pressing mic
  let finalText = "";     // accumulated final transcript for this session
  let userAborted = false;

  function setRecording(on) {
    recording = on;
    micBtn.classList.toggle("is-recording", on);
    micBtn.setAttribute("aria-pressed", on ? "true" : "false");
    micBtn.title = on ? "Listening... click to stop" : "Click to speak";
  }

  micBtn.addEventListener("click", () => {
    if (recording) { userAborted = true; recognition.stop(); return; }
    // Snapshot any text already typed so dictation appends rather than wipes.
    const existing = chatInputEl.value.trimEnd();
    voicePrefix = existing ? existing + " " : "";
    finalText = "";
    userAborted = false;
    try {
      recognition.start();
    } catch (err) {
      // Some browsers throw if start() is called too quickly after a stop.
      appendBubble("error", `mic error: ${err.message || err}`);
    }
  });

  recognition.addEventListener("start", () => setRecording(true));

  recognition.addEventListener("result", (event) => {
    // Walk all results: append finalised chunks to finalText, render the
    // current pending interim chunk live. Overwrite the input each tick so
    // earlier interim guesses do not pile up.
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const r = event.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    chatInputEl.value = voicePrefix + (finalText + interim).trimStart();
  });

  recognition.addEventListener("end", () => {
    setRecording(false);
    if (userAborted) return;
    if (finalText.trim()) {
      // Frictionless: as soon as speech ends with a real transcript, send.
      chatFormEl.requestSubmit();
    }
  });

  recognition.addEventListener("error", (event) => {
    setRecording(false);
    const code = event.error || "unknown";
    if (code === "no-speech") return;   // silent timeout, do not nag
    if (code === "aborted") return;     // user-cancelled
    appendBubble("error", `mic error: ${code}`);
  });
}

setupVoiceInput();

// Onboarding modal: blocks polling until the user submits Name + Age + Activity
// (or until we confirm the session already has a profile from a previous load).
const onboardingModalEl = document.getElementById("onboarding-modal");
const onboardingFormEl = document.getElementById("onboarding-form");
const onboardingNameEl = document.getElementById("onboarding-name");
const onboardingAgeEl = document.getElementById("onboarding-age");
const onboardingActivityEl = document.getElementById("onboarding-activity");
const onboardingSaveEl = document.getElementById("onboarding-save");
const onboardingErrorEl = document.getElementById("onboarding-error");

function isOnboardingValid() {
  const name = onboardingNameEl.value.trim();
  const ageRaw = onboardingAgeEl.value.trim();
  const age = Number.parseInt(ageRaw, 10);
  const activity = onboardingActivityEl.value;
  return name.length > 0
    && ageRaw !== "" && Number.isInteger(age) && age >= 1 && age <= 120
    && activity !== "";
}

function refreshOnboardingSaveState() {
  onboardingSaveEl.disabled = !isOnboardingValid();
}

function showOnboarding() {
  document.body.classList.add("modal-open");
  onboardingModalEl.classList.remove("modal-hidden");
  // Focus name first time the modal opens.
  setTimeout(() => onboardingNameEl.focus(), 0);
}

function hideOnboarding() {
  document.body.classList.remove("modal-open");
  onboardingModalEl.classList.add("modal-hidden");
}

[onboardingNameEl, onboardingAgeEl, onboardingActivityEl].forEach((el) => {
  el.addEventListener("input", refreshOnboardingSaveState);
  el.addEventListener("change", refreshOnboardingSaveState);
});

// Block Escape while the modal is open. No close button is rendered.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.body.classList.contains("modal-open")) {
    e.preventDefault();
    e.stopPropagation();
  }
}, true);

onboardingFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!isOnboardingValid()) return;
  onboardingSaveEl.disabled = true;
  onboardingErrorEl.textContent = "";
  try {
    const body = await postJson("/api/profile", {
      name: onboardingNameEl.value.trim(),
      age: Number.parseInt(onboardingAgeEl.value, 10),
      activity: onboardingActivityEl.value,
    });
    if (!body.ok) {
      onboardingErrorEl.textContent = body.error || "Could not save profile.";
      onboardingSaveEl.disabled = false;
      return;
    }
    hideOnboarding();
    startPolling();
  } catch (err) {
    onboardingErrorEl.textContent = err.message || "Network error. Try again.";
    onboardingSaveEl.disabled = false;
  }
});

let pollingStarted = false;
function startPolling() {
  if (pollingStarted) return;
  pollingStarted = true;
  setStatus("idle", "starting…");
  pollLoop();
  setInterval(pollLoop, POLL_MS);
}

(async function bootstrap() {
  try {
    const res = await fetch("/api/profile", { cache: "no-store" });
    const body = await res.json();
    if (body && body.ok && body.set) {
      hideOnboarding();
      startPolling();
      return;
    }
  } catch (_e) {
    // Network or server hiccup: still show the modal so the user can proceed.
  }
  showOnboarding();
})();
