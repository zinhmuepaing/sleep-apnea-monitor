"use strict";

const I18N = {
  en: {
    dashboard_title:        "Health Monitor Dashboard",
    download_csv_btn:       "Download Data",
    bpm_label:              "BPM",
    spo2_label:             "SpO₂",
    verdict_label:          "Verdict",
    label_spo2_status:      "SpO₂ status",
    label_bpm_status:       "BPM status",
    label_avg_spo2:         "Avg SpO₂",
    label_avg_bpm:          "Avg BPM",
    label_window:           "Window",
    label_anomaly:          "Anomaly",
    anomaly_banner_title:   "Anomaly detected.",
    talk_to_kirby_btn:      "Talk to Kirby",
    ask_kirby_btn:          "Ask Kirby",
    disclaimer:             "This is wellness coaching, not medical advice.",
    chat_subtitle:          "Sleep & cardiac companion",
    chat_placeholder:       "Message Kirby...",
    map_panel_title:        "Route to Clinic",
    map_driving:            "Driving",
    map_transit:            "Transit",
    map_walking:            "Walking",
    map_cycling:            "Cycling",
    onboarding_title:       "Welcome. Let's calibrate.",
    onboarding_disclaimer:  "Your name and age calibrate baseline heart-rate and SpO₂ thresholds, and label your CSV exports.",
    onboarding_th_age_range:"Age range",
    onboarding_th_bpm:      "BPM",
    onboarding_th_spo2:     "SpO₂",
    onboarding_row_0_3:     "0–3 yrs (Infants/Toddlers)",
    onboarding_row_4_11:    "4–11 yrs (Children)",
    onboarding_row_12_64:   "12–64 yrs (Teens/Adults)",
    onboarding_row_65:      "65+ yrs (Seniors)",
    onboarding_name:        "Name",
    onboarding_age:         "Age",
    onboarding_activity:    "Activity level",
    onboarding_choose:      "Choose one",
    onboarding_activity_sedentary: "Sedentary",
    onboarding_activity_light:     "Lightly active",
    onboarding_activity_moderate:  "Moderately active",
    onboarding_activity_very:      "Very active",
    onboarding_save:        "Save Changes",
    status_idle:            "idle",
    status_polling:         "polling",
    status_connected:       "connected",
    status_error:           "error",
    pill_none:              "none",
    pill_normal:            "normal",
    pill_borderline:        "borderline",
    pill_low:               "low",
    pill_lower:             "lower",
    pill_optimal:           "optimal",
    pill_higher:            "higher",
    pill_spo2_low:          "spo2 low",
    pill_spo2_borderline:   "spo2 borderline",
    pill_bpm_low:           "bpm low",
    pill_bpm_high:          "bpm high",
    detail_no_finger:       "no finger",
    detail_last:            "last",
    detail_starting:        "starting…",
  },
  zh: {
    dashboard_title:        "健康监测仪表板",
    download_csv_btn:       "下载 CSV",
    bpm_label:              "心率",
    spo2_label:             "血氧饱和度",
    verdict_label:          "诊断结果",
    label_spo2_status:      "血氧状态",
    label_bpm_status:       "心率状态",
    label_avg_spo2:         "平均血氧",
    label_avg_bpm:          "平均心率",
    label_window:           "窗口",
    label_anomaly:          "异常",
    anomaly_banner_title:   "检测到异常。",
    talk_to_kirby_btn:      "与 Kirby 对话",
    ask_kirby_btn:          "问问 Kirby",
    disclaimer:             "这是健康建议，不构成医疗意见。",
    chat_subtitle:          "睡眠与心脏伴侣",
    chat_placeholder:       "给 Kirby 发消息…",
    map_panel_title:        "前往诊所的路线",
    map_driving:            "驾车",
    map_transit:            "公交",
    map_walking:            "步行",
    map_cycling:            "骑行",
    onboarding_title:       "欢迎。让我们校准。",
    onboarding_disclaimer:  "您的姓名和年龄用于校准心率与血氧阈值，并标记 CSV 导出文件。",
    onboarding_th_age_range:"年龄范围",
    onboarding_th_bpm:      "心率",
    onboarding_th_spo2:     "血氧",
    onboarding_row_0_3:     "0–3 岁（婴幼儿）",
    onboarding_row_4_11:    "4–11 岁（儿童）",
    onboarding_row_12_64:   "12–64 岁（青年与成人）",
    onboarding_row_65:      "65+ 岁（老年人）",
    onboarding_name:        "姓名",
    onboarding_age:         "年龄",
    onboarding_activity:    "活动水平",
    onboarding_choose:      "请选择",
    onboarding_activity_sedentary: "久坐",
    onboarding_activity_light:     "轻度活动",
    onboarding_activity_moderate:  "中等活动",
    onboarding_activity_very:      "高度活动",
    onboarding_save:        "保存",
    status_idle:            "空闲",
    status_polling:         "检测中",
    status_connected:       "已连接",
    status_error:           "错误",
    pill_none:              "无",
    pill_normal:            "正常",
    pill_borderline:        "临界",
    pill_low:               "偏低",
    pill_lower:             "偏低",
    pill_optimal:           "正常",
    pill_higher:            "偏高",
    pill_spo2_low:          "血氧偏低",
    pill_spo2_borderline:   "血氧临界",
    pill_bpm_low:           "心率偏低",
    pill_bpm_high:          "心率偏高",
    detail_no_finger:       "未检测到手指",
    detail_last:            "最后",
    detail_starting:        "启动中…",
  }
};

let _currentLang = localStorage.getItem('kirby_lang') || 'en';
function t(key) {
  const dict = I18N[_currentLang] || I18N.en;
  return dict[key] !== undefined ? dict[key] : (I18N.en[key] !== undefined ? I18N.en[key] : key);
}

// Rank a voice on "naturalness". Higher score wins. Browser-default cloud
// voices (Chrome's "Google ..." and Edge's "Microsoft ... Natural / Online")
// are the smooth, human-sounding ones. Local OS voices (eSpeak, SAPI Zira)
// are the robotic ones we want to avoid when a better option exists.
function _voiceNaturalnessScore(v) {
  const name = (v.name || "").toLowerCase();
  let s = 0;
  if (name.includes("natural")) s += 100;          // Edge "...Natural"
  if (name.includes("online"))  s += 90;           // Edge "...Online (Natural)"
  if (name.includes("neural"))  s += 90;
  if (name.startsWith("google")) s += 80;          // Chrome cloud voices
  if (name.includes("premium")) s += 60;
  if (name.includes("enhanced")) s += 60;
  if (v.localService === false) s += 30;           // remote voices > local
  // Female-sounding name hints (Kirby is voiced female).
  const FEMALE = ["samantha","victoria","karen","moira","tessa","fiona","serena",
                  "allison","ava","susan","zira","aria","jenny","emma","libby",
                  "xiaoxiao","xiaoyi","yaoyao","huihui","tracy","hanhan"];
  if (FEMALE.some(h => name.includes(h))) s += 10;
  return s;
}

function _pickBestVoice(langPrefix, langExact) {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;
  const matches = voices.filter(v => {
    const l = (v.lang || "").toLowerCase();
    return l === langExact || l.startsWith(langPrefix);
  });
  if (!matches.length) return null;
  matches.sort((a, b) => _voiceNaturalnessScore(b) - _voiceNaturalnessScore(a));
  const best = matches[0];
  // If the best candidate has no natural/cloud markers, return null so the
  // browser falls back to its own default (usually higher quality than a
  // local SAPI/eSpeak voice we'd otherwise lock in).
  if (_voiceNaturalnessScore(best) < 30) return null;
  return best;
}

function _pickEnglishVoice()  { return _pickBestVoice("en", "en-us"); }
function _pickMandarinVoice() { return _pickBestVoice("zh", "zh-cn"); }

function _selectMandarinVoice() { window._ttsVoice = _pickMandarinVoice(); }
function _selectEnglishVoice()  { window._ttsVoice = _pickEnglishVoice(); }

function _refreshVoiceForCurrentLang() {
  if (_currentLang === "zh") _selectMandarinVoice();
  else _selectEnglishVoice();
}

if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = _refreshVoiceForCurrentLang;
}

function applyLang(lang) {
  _currentLang = lang;
  localStorage.setItem('kirby_lang', lang);
  document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-CN' : 'en');

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = t(key);
    if (val !== undefined) el.textContent = val;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    const val = t(key);
    if (val !== undefined) el.placeholder = val;
  });

  const btn = document.getElementById('lang-toggle-btn');
  if (btn) btn.textContent = lang === 'en' ? '中文' : 'English';

  if (window._recognition) {
    try { window._recognition.abort(); } catch (_e) { /* ignore */ }
    window._recognition.lang = lang === 'zh' ? 'zh-CN' : 'en-US';
  }
  // Cancel any utterance still queued from the previous language so a stale
  // Mandarin payload does not get re-spoken under an English locale (which
  // silently fails on most browsers).
  if ("speechSynthesis" in window) {
    try { window.speechSynthesis.cancel(); } catch (_e) { /* ignore */ }
  }
  _refreshVoiceForCurrentLang();

  // Refresh dynamic UI (status pill, verdict pills, banner) so their current
  // state re-renders with the new language.
  if (typeof _lastStatusState === 'string') {
    setStatus(_lastStatusState, _lastStatusDetail);
  }
  if (lastVerdict) renderVerdict(lastVerdict);
}

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
        window._userLat = userCoords.lat;
        window._userLng = userCoords.lon;
        resolve(userCoords);
      },
      () => { resolve(null); },   // declined or unavailable
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 5 * 60 * 1000 }
    );
  }).finally(() => { geoInFlight = null; });

  return geoInFlight;
}

let _lastStatusState = "idle";
let _lastStatusDetail = "";

function setStatus(state, detail = "") {
  _lastStatusState = state;
  _lastStatusDetail = detail;
  pillEl.className = `pill pill-${state}`;
  const labelKey = `status_${state}`;
  pillEl.textContent = (I18N[_currentLang] && I18N[_currentLang][labelKey]) || state;
  // Translate well-known detail strings; leave free-form text as-is.
  detailEl.textContent = _translateDetail(detail);
}

function _translateDetail(detail) {
  if (!detail) return "";
  if (detail === "no finger") return t("detail_no_finger");
  if (detail === "starting…") return t("detail_starting");
  const m = detail.match(/^last\s+(.+)$/);
  if (m) return `${t("detail_last")} ${m[1]}`;
  return detail;
}

function _translatePillText(rawState) {
  // rawState is the server-supplied label like "normal", "borderline", "low",
  // "lower", "optimal", "higher", "none", "spo2_low", "bpm_high", etc.
  const key = `pill_${rawState}`;
  const val = t(key);
  return val === key ? rawState : val;
}

function setPill(el, state, text) {
  el.className = `pill pill-${state}`;
  el.textContent = _translatePillText(text);
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

// Pick rate + pitch from the text's tone. Subtle deltas only; we want
// "more human" not "performative". Excited text speeds up and lifts the
// pitch a hair; concerned text slows down and drops a hair.
const _CONCERN_RE_EN = /\b(clinician|doctor|please see|concern|worried|low|please|carefully|persistent|sorry)\b/i;
const _EXCITE_RE_EN  = /\b(great|nice|awesome|amazing|wonderful|love|yay|excellent|good job|well done|perfect|fantastic|happy)\b/i;
const _CONCERN_RE_ZH = /(医生|临床|请咨询|担心|注意|抱歉|偏低|建议)/;
const _EXCITE_RE_ZH  = /(太好了|真棒|不错|很好|做得好|开心|完美|加油)/;

function _toneFor(text, lang) {
  const hasBang = /!/.test(text);
  const isZh = lang === "zh";
  const exciteRe  = isZh ? _EXCITE_RE_ZH  : _EXCITE_RE_EN;
  const concernRe = isZh ? _CONCERN_RE_ZH : _CONCERN_RE_EN;

  let rate  = isZh ? 0.96 : 1.0;   // Mandarin reads a touch slower for clarity
  let pitch = 1.0;

  if (hasBang || exciteRe.test(text)) {
    rate  += 0.05;
    pitch += 0.06;
  } else if (concernRe.test(text)) {
    rate  -= 0.05;
    pitch -= 0.03;
  }
  // Clamp to safe, natural range.
  rate  = Math.max(0.85, Math.min(1.15, rate));
  pitch = Math.max(0.9,  Math.min(1.15, pitch));
  return { rate, pitch };
}

// Split a reply into clauses on sentence-ending punctuation so the engine
// inserts a genuine breath between them. Commas stay inside clauses; the
// engine already shortens its pause there. Empty clauses are dropped.
function _splitClauses(text, lang) {
  if (!text) return [];
  // Treat CJK punctuation (。！？) as well as ASCII.
  const re = lang === "zh"
    ? /[^。！？!?]+[。！？!?]?/g
    : /[^.!?]+[.!?]?/g;
  const parts = text.match(re) || [text];
  return parts.map(s => s.trim()).filter(Boolean);
}

function speak(text) {
  if (!("speechSynthesis" in window) || !text) return;
  window.speechSynthesis.cancel();

  // English: match the sleep-apnea-monitor reference. Minimal utterance,
  // no voice override, rate 1.0 + pitch 1.2 for playful Kirby. The browser
  // picks its default natural English voice (e.g. Chrome's Google US English).
  if (_currentLang !== "zh") {
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.0;
    u.pitch = 1.2;
    window.speechSynthesis.speak(u);
    return;
  }

  // Mandarin: keep the natural-voice picker + clause splitting + tone shaping.
  if (!window._ttsVoice) _refreshVoiceForCurrentLang();
  const { rate, pitch } = _toneFor(text, "zh");
  const clauses = _splitClauses(text, "zh");
  for (const clause of clauses) {
    const u = new SpeechSynthesisUtterance(clause);
    u.lang  = "zh-CN";
    u.rate  = rate;
    u.pitch = pitch;
    u.volume = 1.0;
    if (window._ttsVoice) u.voice = window._ttsVoice;
    window.speechSynthesis.speak(u);
  }
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

const BOOKING_CONFIRMATION_RE =
  /you(?:'ve)? chose?n?\s+(.+?)\.\s*(check your phone|booking link)/i;
const MAP_META_RE = /%%MAP_META%%(\{[\s\S]*?\})%%END_META%%/;

// Strip the %%MAP_META%% block from a reply and return { text, meta }.
function extractMapMeta(reply) {
  const m = reply && reply.match(MAP_META_RE);
  if (!m) return { text: reply, meta: null };
  let meta = null;
  try { meta = JSON.parse(m[1]); } catch (_e) { meta = null; }
  const text = reply.replace(MAP_META_RE, "").trim();
  return { text, meta };
}

// Fire openMapPanel when a booking is confirmed. Prefer the backend's
// MAP_META coordinates; otherwise fall back to regex-only and let the
// map centre on the clinic via geocode skip.
function maybeOpenMapFromReply(cleanText, meta) {
  if (meta && typeof meta.lat === "number" && typeof meta.lng === "number") {
    openMapPanel(meta.name || "", meta.lat, meta.lng);
    return;
  }
  const m = cleanText && cleanText.match(BOOKING_CONFIRMATION_RE);
  if (m) openMapPanel(m[1].trim(), null, null);
}

chatFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  let text = chatInputEl.value.trim();
  if (!text) return;

  let echoed = false;

  // 1. Pending-correction resolver. If a fuzzy match suggestion is open,
  // intercept "yes" / "no" and either substitute the match name or clear.
  if (window._pendingClinicMatch) {
    const lower = text.toLowerCase();
    if (lower === "yes" || lower === "y") {
      const matched = window._pendingClinicMatch.name;
      window._pendingClinicMatch = null;
      appendBubble("user", text);
      chatInputEl.value = "";
      echoed = true;
      text = matched;
      // fall through to send the corrected name
    } else if (lower === "no" || lower === "n") {
      window._pendingClinicMatch = null;
      appendBubble("user", text);
      chatInputEl.value = "";
      appendBubble("kirby", "No problem. Please retype the clinic name.");
      return;
    }
  }

  // 2. Fuzzy clinic-name pre-check. Only on plain-looking messages that
  // could be a clinic name. Skipped on the post-substitution path.
  if (
    !echoed &&
    !window._pendingClinicMatch &&
    text.length >= 3 && text.length <= 60 && !text.startsWith("/")
  ) {
    try {
      const matchBody = await postJson("/api/clinic_match", { query: text });
      if (matchBody && matchBody.ok && matchBody.confident === false && matchBody.match) {
        window._pendingClinicMatch = matchBody.match;
        appendBubble("user", text);
        chatInputEl.value = "";
        appendBubble(
          "kirby",
          `Did you mean ${matchBody.match.name}? Reply 'yes' to confirm or 'no' to try again.`
        );
        return;
      }
      // If ok=false with "no clinics in session", just continue silently.
    } catch (_e) {
      // network hiccup on pre-check: skip and send normally
    }
  }

  if (!echoed) {
    appendBubble("user", text);
    chatInputEl.value = "";
  }

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
    payload.lang = _currentLang;
    const body = await postJson("/api/chat/message", payload);
    if (body.ok) {
      const { text: cleanReply, meta } = extractMapMeta(body.text || "");
      appendBubble("kirby", cleanReply);
      speak(cleanReply);
      if (body.links && body.links.length) appendLinksBubble(body.links);
      maybeOpenMapFromReply(cleanReply, meta);
    } else {
      appendBubble("error", body.error || "Kirby is quiet right now.");
    }
  } catch (err) {
    appendBubble("error", err.message || "network error");
  }
});

async function fireKirbyAlert(verdict, profile) {
  try {
    const body = await postJson("/api/chat/alert", { verdict, profile, lang: _currentLang });
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
    const anomalyText = _translatePillText(verdict.anomaly_type);
    bannerTextEl.textContent = `${t("label_anomaly")}: ${anomalyText}.`;
  } else {
    bannerEl.classList.add("banner-hidden");
    bannerTextEl.textContent = t("anomaly_banner_title");
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
  window._recognition = recognition;
  recognition.lang = _currentLang === 'zh' ? 'zh-CN' : 'en-US';
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

// --- Map Panel ---

const MAP_PANEL      = document.getElementById("map-panel");
const MAP_IFRAME     = document.getElementById("map-iframe");
const MAP_CLOSE_BTN  = document.getElementById("map-panel-close");
const MAP_MODE_BTNS  = document.querySelectorAll(".map-mode-btn");

let _mapState = {
  clinicLat: null, clinicLng: null,
  userLat: null,   userLng: null,
  activeMode: "driving",
};

function getUserPosition() {
  if (window._userLat != null && window._userLng != null) {
    return Promise.resolve({ lat: window._userLat, lng: window._userLng });
  }
  if (userCoords) {
    return Promise.resolve({ lat: userCoords.lat, lng: userCoords.lon });
  }
  if (!("geolocation" in navigator)) {
    return Promise.resolve({ lat: null, lng: null });
  }
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve({ lat: null, lng: null }),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 5 * 60 * 1000 }
    );
  });
}

function _clinicOnlyEmbed(lat, lng) {
  const q = encodeURIComponent(`${lat},${lng}`);
  return `https://www.google.com/maps?q=${q}&output=embed`;
}

async function loadMapIframe(mode) {
  if (_mapState.clinicLat == null || _mapState.clinicLng == null) return;

  // If user location is missing, centre the iframe on the clinic only and
  // tell the user why no route is showing.
  if (_mapState.userLat == null || _mapState.userLng == null) {
    MAP_IFRAME.src = _clinicOnlyEmbed(_mapState.clinicLat, _mapState.clinicLng);
    appendBubble("error", "Showing the clinic location only. Allow location access in the browser to see the route.");
    return;
  }

  try {
    const res = await fetch("/api/map_embed_url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_lat: _mapState.clinicLat, clinic_lng: _mapState.clinicLng,
        user_lat:   _mapState.userLat,   user_lng:   _mapState.userLng,
        mode,
      }),
    });
    const data = await res.json();
    if (data && data.ok) {
      MAP_IFRAME.src = data.embed_url;
      return;
    }
    MAP_IFRAME.src = _clinicOnlyEmbed(_mapState.clinicLat, _mapState.clinicLng);
    appendBubble("error", `Map route unavailable: ${data && data.error ? data.error : "unknown server error"}. Showing clinic only.`);
  } catch (e) {
    MAP_IFRAME.src = _clinicOnlyEmbed(_mapState.clinicLat, _mapState.clinicLng);
    appendBubble("error", `Map route fetch failed: ${e.message || e}. Showing clinic only.`);
  }
}

async function openMapPanel(clinicName, clinicLat, clinicLng) {
  if (clinicLat == null || clinicLng == null) {
    // Without coords we cannot point the map. Skip rather than render blank.
    return;
  }
  const pos = await getUserPosition();
  _mapState = {
    clinicLat, clinicLng,
    userLat: pos.lat, userLng: pos.lng,
    activeMode: "driving",
  };
  MAP_MODE_BTNS.forEach((b) => b.classList.toggle("active", b.dataset.mode === "driving"));
  await loadMapIframe("driving");
  MAP_PANEL.classList.add("map-panel--open");
  MAP_PANEL.setAttribute("aria-hidden", "false");
  document.documentElement.style.setProperty(
    "--map-panel-offset", MAP_PANEL.offsetWidth + "px"
  );
}

function closeMapPanel() {
  MAP_PANEL.classList.remove("map-panel--open");
  MAP_PANEL.setAttribute("aria-hidden", "true");
  MAP_IFRAME.src = "about:blank";
  document.documentElement.style.setProperty("--map-panel-offset", "0px");
}

if (MAP_CLOSE_BTN) MAP_CLOSE_BTN.addEventListener("click", closeMapPanel);

MAP_MODE_BTNS.forEach((btn) => {
  btn.addEventListener("click", async () => {
    MAP_MODE_BTNS.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    _mapState.activeMode = btn.dataset.mode;
    await loadMapIframe(btn.dataset.mode);
  });
});

applyLang(_currentLang);
const _langToggleBtn = document.getElementById('lang-toggle-btn');
if (_langToggleBtn) {
  _langToggleBtn.addEventListener('click', () => {
    applyLang(_currentLang === 'en' ? 'zh' : 'en');
  });
}

(async function bootstrap() {
  // Ask the browser for geolocation eagerly so a route is available the
  // moment a booking confirmation arrives. Failure is silent here — the
  // user can still grant later via the chat flow.
  requestGeolocation();

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
