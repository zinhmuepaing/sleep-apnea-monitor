#include <Wire.h>
#include <MAX30105.h>
#include <heartRate.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include "secrets.h"

MAX30105 particleSensor;
TFT_eSPI tft = TFT_eSPI();
AsyncWebServer server(80);

const byte RATE_SIZE = 10;
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;
float beatsPerMinute;
int beatAvg = 0;
float ESpO2 = 0;

#define FINGER_ON 30000
#define FINGER_OFF_COUNT 10  // require this many low samples before declaring finger off

bool fingerPresent = false;
int fingerOffCounter = 0;

// =========================================================================
// THEME + UI HELPERS
// All drawing is presentation only. None of this touches sensor math, the
// MAX30102 ISR path, the WiFi setup, or the /data JSON endpoint.
// =========================================================================

// Layout constants for the active dashboard. Pre-computed so loop() can
// repaint just the inner numeric region without redrawing the card frames.
#define HEADER_H        22
#define BPM_CARD_X      4
#define BPM_CARD_Y      28
#define BPM_CARD_W      114
#define BPM_CARD_H      104
#define SPO2_CARD_X     122
#define SPO2_CARD_Y     28
#define SPO2_CARD_W     114
#define SPO2_CARD_H     104
#define STATUS_STRIP_H  8
#define BEAT_DOT_X      (BPM_CARD_X + BPM_CARD_W - 8)
#define BEAT_DOT_Y      (BPM_CARD_Y + 6)
#define BEAT_DOT_R      4

// Inner numeric regions (cleared each tick).
#define BPM_VALUE_X     (BPM_CARD_X + 4)
#define BPM_VALUE_Y     (BPM_CARD_Y + 32)
#define BPM_VALUE_W     (BPM_CARD_W - 8)
#define BPM_VALUE_H     50
#define SPO2_VALUE_X    (SPO2_CARD_X + 4)
#define SPO2_VALUE_Y    (SPO2_CARD_Y + 32)
#define SPO2_VALUE_W    (SPO2_CARD_W - 8)
#define SPO2_VALUE_H    50

uint16_t COL_BG, COL_HEADER_BG, COL_HEADER_FG;
uint16_t COL_CARD_BG, COL_CARD_BORDER, COL_LABEL, COL_SUBLABEL;
uint16_t COL_BPM_ACCENT, COL_SPO2_ACCENT, COL_VALUE;
uint16_t COL_STATUS_GOOD, COL_STATUS_WARN, COL_STATUS_BAD, COL_STATUS_IDLE;

void initTheme() {
  COL_BG          = TFT_BLACK;
  COL_HEADER_BG   = tft.color565(18, 28, 48);     // slate navy
  COL_HEADER_FG   = tft.color565(120, 220, 255);  // cyan
  COL_CARD_BG     = tft.color565(14, 18, 28);     // near-black panel
  COL_CARD_BORDER = tft.color565(40, 56, 84);     // muted slate
  COL_LABEL       = tft.color565(160, 180, 210);  // soft grey-blue
  COL_SUBLABEL    = tft.color565(110, 125, 150);
  COL_BPM_ACCENT  = tft.color565(240, 70, 90);    // medical red
  COL_SPO2_ACCENT = tft.color565(80, 200, 230);   // cyan
  COL_VALUE       = TFT_WHITE;
  COL_STATUS_GOOD = tft.color565(60, 200, 120);   // green
  COL_STATUS_WARN = tft.color565(240, 180, 60);   // amber
  COL_STATUS_BAD  = tft.color565(240, 70, 90);    // red
  COL_STATUS_IDLE = tft.color565(60, 70, 90);     // slate
}

void drawHeaderBar(const char* title) {
  tft.fillRect(0, 0, 240, HEADER_H, COL_HEADER_BG);
  tft.fillRect(0, HEADER_H, 240, 1, COL_CARD_BORDER);
  tft.setTextColor(COL_HEADER_FG, COL_HEADER_BG);
  tft.setTextSize(1);
  tft.drawCentreString(title, 120, 7, 2);
}

void drawCardFrame(int x, int y, int w, int h, uint16_t border, uint16_t fill) {
  tft.fillRoundRect(x, y, w, h, 6, fill);
  tft.drawRoundRect(x, y, w, h, 6, border);
}

// Heart with an ECG line running through it. Centred at (cx, cy).
// Heart silhouette ~16 wide x 14 tall. Two lobes + triangle point.
void drawHeartEcgIcon(int cx, int cy, uint16_t heartCol, uint16_t ecgCol) {
  // Lobes
  tft.fillCircle(cx - 4, cy - 2, 4, heartCol);
  tft.fillCircle(cx + 4, cy - 2, 4, heartCol);
  // Point (triangle stretching down)
  tft.fillTriangle(cx - 7, cy,  cx + 7, cy,  cx, cy + 8, heartCol);

  // ECG polyline across the heart's middle. Five segments: flat, small bump,
  // sharp spike up, sharp spike down, return to flat.
  int y0 = cy + 1;
  tft.drawLine(cx - 8, y0,     cx - 5, y0,     ecgCol);
  tft.drawLine(cx - 5, y0,     cx - 3, y0 - 2, ecgCol);
  tft.drawLine(cx - 3, y0 - 2, cx,     y0 - 6, ecgCol);
  tft.drawLine(cx,     y0 - 6, cx + 3, y0 + 3, ecgCol);
  tft.drawLine(cx + 3, y0 + 3, cx + 8, y0,     ecgCol);
}

// Teardrop with "O2" label. Centred at (cx, cy). About 14 wide x 18 tall.
void drawDropletO2Icon(int cx, int cy, uint16_t dropCol, uint16_t textCol) {
  // Round bottom
  tft.fillCircle(cx, cy + 2, 6, dropCol);
  // Pointed top
  tft.fillTriangle(cx - 5, cy + 1,  cx + 5, cy + 1,  cx, cy - 8, dropCol);

  // "O2" label below the droplet. The "2" sits one pixel lower so it reads
  // as a subscript even at size 1.
  tft.setTextSize(1);
  tft.setTextColor(textCol, COL_CARD_BG);
  tft.drawString("O", cx - 6, cy + 11, 1);
  tft.drawString("2", cx + 1, cy + 13, 1);
}

void drawStatusStrip(int x, int y, int w, int h, uint16_t col) {
  tft.fillRect(x, y, w, h, col);
}

uint16_t bpmStatusColor(int bpm) {
  if (bpm <= 0) return COL_STATUS_IDLE;
  if (bpm >= 60 && bpm <= 100) return COL_STATUS_GOOD;
  if ((bpm >= 50 && bpm < 60) || (bpm > 100 && bpm <= 110)) return COL_STATUS_WARN;
  return COL_STATUS_BAD;
}

uint16_t spo2StatusColor(float spo2) {
  if (spo2 < 80) return COL_STATUS_IDLE;
  if (spo2 >= 95) return COL_STATUS_GOOD;
  if (spo2 >= 92) return COL_STATUS_WARN;
  return COL_STATUS_BAD;
}

// =========================================================================
// SCREENS
// =========================================================================

void drawPlaceFingerScreen() {
  tft.fillScreen(COL_BG);
  drawHeaderBar("HEALTH MONITOR");

  // Centred prompt card.
  int cx = 20, cy = 32, cw = 200, ch = 96;
  drawCardFrame(cx, cy, cw, ch, COL_CARD_BORDER, COL_CARD_BG);

  // Heart-ECG icon top of card.
  drawHeartEcgIcon(cx + cw / 2, cy + 22, COL_BPM_ACCENT, COL_VALUE);

  // Headline
  tft.setTextColor(TFT_YELLOW, COL_CARD_BG);
  tft.setTextSize(2);
  tft.drawCentreString("PLACE FINGER", cx + cw / 2, cy + 44, 1);

  // Subline
  tft.setTextSize(1);
  tft.setTextColor(COL_SUBLABEL, COL_CARD_BG);
  tft.drawCentreString("Touch sensor to begin", cx + cw / 2, cy + 70, 1);
}

void drawReadingScreen() {
  tft.fillScreen(COL_BG);
  drawHeaderBar("HEALTH MONITOR");

  // BPM card.
  drawCardFrame(BPM_CARD_X, BPM_CARD_Y, BPM_CARD_W, BPM_CARD_H, COL_CARD_BORDER, COL_CARD_BG);
  drawHeartEcgIcon(BPM_CARD_X + 14, BPM_CARD_Y + 14, COL_BPM_ACCENT, COL_VALUE);
  tft.setTextSize(1);
  tft.setTextColor(COL_LABEL, COL_CARD_BG);
  tft.drawString("BPM", BPM_CARD_X + 30, BPM_CARD_Y + 11, 1);

  // SpO2 card.
  drawCardFrame(SPO2_CARD_X, SPO2_CARD_Y, SPO2_CARD_W, SPO2_CARD_H, COL_CARD_BORDER, COL_CARD_BG);
  drawDropletO2Icon(SPO2_CARD_X + 14, SPO2_CARD_Y + 14, COL_SPO2_ACCENT, COL_VALUE);
  tft.setTextSize(1);
  tft.setTextColor(COL_LABEL, COL_CARD_BG);
  tft.drawString("SpO2", SPO2_CARD_X + 30, SPO2_CARD_Y + 11, 1);
}

void drawWifiSplash(const String& line1, const String& line2) {
  tft.fillScreen(COL_BG);
  drawHeaderBar("HEALTH MONITOR");

  int cx = 20, cy = 38, cw = 200, ch = 80;
  drawCardFrame(cx, cy, cw, ch, COL_CARD_BORDER, COL_CARD_BG);

  tft.setTextColor(COL_LABEL, COL_CARD_BG);
  tft.setTextSize(1);
  tft.drawCentreString(line1, cx + cw / 2, cy + 16, 2);

  tft.setTextColor(COL_STATUS_GOOD, COL_CARD_BG);
  tft.setTextSize(1);
  tft.drawCentreString(line2, cx + cw / 2, cy + 46, 2);
}

void startWebServer() {
  server.on("/data", HTTP_GET, [](AsyncWebServerRequest *request) {
    String json = "{";
    json += "\"bpm\":";
    json += (fingerPresent && beatAvg > 0) ? String(beatAvg) : "0";
    json += ",\"spo2\":";
    json += (fingerPresent && ESpO2 > 80) ? String(ESpO2, 1) : "0.0";
    json += "}";
    request->send(200, "application/json", json);
  });
  server.begin();
}

void setup() {
  Serial.begin(115200);
  btStop();

  Wire.begin(21, 22);
  Wire.setClock(I2C_SPEED_FAST);

  pinMode(4, OUTPUT);
  digitalWrite(4, HIGH);
  tft.init();
  tft.setRotation(1);
  initTheme();

  drawWifiSplash("Connecting WiFi", String(WIFI_SSID));
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 20000) {
    delay(500);
    Serial.print(".");
  }

  String ipLine;
  if (WiFi.status() == WL_CONNECTED) {
    ipLine = WiFi.localIP().toString();
    Serial.print("\nWiFi connected. IP: ");
    Serial.println(ipLine);
    startWebServer();
  } else {
    ipLine = "WiFi failed";
    Serial.println("\nWiFi connect failed; continuing offline.");
  }
  drawWifiSplash("IP", ipLine);
  delay(2500);

  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_RED);
    tft.drawCentreString("SENSOR NOT FOUND", 120, 60, 2);
    while (1);
  }

  byte ledBrightness = 0x1F;
  byte sampleAverage = 8;
  byte ledMode = 2;
  int sampleRate = 400;
  int pulseWidth = 411;
  int adcRange = 4096;
  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);

  drawPlaceFingerScreen();
}

void loop() {
  particleSensor.check();

  while (particleSensor.available()) {
    long irValue = particleSensor.getFIFOIR();
    long redValue = particleSensor.getFIFORed();
    particleSensor.nextSample();

    // Finger detection with hysteresis
    if (irValue < FINGER_ON) {
      fingerOffCounter++;
      if (fingerOffCounter >= FINGER_OFF_COUNT && fingerPresent) {
        fingerPresent = false;
        beatAvg = 0;
        ESpO2 = 0;
        rateSpot = 0;
        for (byte x = 0; x < RATE_SIZE; x++) rates[x] = 0;
        drawPlaceFingerScreen();
      }
      continue;
    } else {
      fingerOffCounter = 0;
      if (!fingerPresent) {
        fingerPresent = true;
        drawReadingScreen();
      }
    }

    // Heart Rate Calculation
    if (checkForBeat(irValue) == true) {
      tft.fillCircle(BEAT_DOT_X, BEAT_DOT_Y, BEAT_DOT_R, COL_BPM_ACCENT);
      long delta = millis() - lastBeat;
      lastBeat = millis();
      beatsPerMinute = 60.0 / (delta / 1000.0);

      if (beatsPerMinute >= 35 && beatsPerMinute < 200) {
        rates[rateSpot++] = (byte)beatsPerMinute;
        rateSpot %= RATE_SIZE;
        long sum = 0;
        byte validCount = 0;
        for (byte x = 0; x < RATE_SIZE; x++) {
          if (rates[x] > 0) {
            sum += rates[x];
            validCount++;
          }
        }
        if (validCount > 0) beatAvg = sum / validCount;
      }
    }

    // SpO2 Calculation
    if (irValue > 0) {
      double ratio = (double)redValue / (double)irValue;
      float currentSpO2 = -45.06 * ratio * ratio + 30.354 * ratio + 94.845;
      if (currentSpO2 > 100) currentSpO2 = 100;
      if (currentSpO2 > 80) {
        if (ESpO2 == 0) ESpO2 = currentSpO2;
        else ESpO2 = (ESpO2 * 0.95) + (currentSpO2 * 0.05);
      }
    }
  }

  // Clear pulse circle if no beat detected recently
  if (fingerPresent && millis() - lastBeat > 600) {
    tft.fillCircle(BEAT_DOT_X, BEAT_DOT_Y, BEAT_DOT_R, COL_CARD_BG);
  }

  // Update display only when finger is present
  static unsigned long lastUpdate = 0;
  if (fingerPresent && millis() - lastUpdate > 300) {
    // Repaint only the inner numeric regions; card frames + icons + labels
    // were painted once by drawReadingScreen on the finger-on transition.
    tft.fillRect(BPM_VALUE_X, BPM_VALUE_Y, BPM_VALUE_W, BPM_VALUE_H, COL_CARD_BG);
    tft.fillRect(SPO2_VALUE_X, SPO2_VALUE_Y, SPO2_VALUE_W, SPO2_VALUE_H, COL_CARD_BG);

    // BPM big number
    tft.setTextColor(COL_VALUE, COL_CARD_BG);
    tft.setTextSize(5);
    char bpmBuf[8];
    if (beatAvg > 0) snprintf(bpmBuf, sizeof(bpmBuf), "%d", beatAvg);
    else             snprintf(bpmBuf, sizeof(bpmBuf), "--");
    tft.drawCentreString(bpmBuf, BPM_CARD_X + BPM_CARD_W / 2, BPM_VALUE_Y + 6, 1);

    // SpO2 big number with % suffix
    tft.setTextColor(COL_VALUE, COL_CARD_BG);
    tft.setTextSize(5);
    char spo2Buf[8];
    if (ESpO2 > 80) snprintf(spo2Buf, sizeof(spo2Buf), "%d", (int)ESpO2);
    else            snprintf(spo2Buf, sizeof(spo2Buf), "--");
    tft.drawCentreString(spo2Buf, SPO2_CARD_X + SPO2_CARD_W / 2 - 8, SPO2_VALUE_Y + 6, 1);
    tft.setTextSize(2);
    tft.setTextColor(COL_SPO2_ACCENT, COL_CARD_BG);
    if (ESpO2 > 80) tft.drawString("%", SPO2_CARD_X + SPO2_CARD_W - 22, SPO2_VALUE_Y + 22, 1);

    // Status strips at the bottom of each card
    drawStatusStrip(BPM_CARD_X + 1,  BPM_CARD_Y + BPM_CARD_H - STATUS_STRIP_H - 1,
                    BPM_CARD_W - 2,  STATUS_STRIP_H, bpmStatusColor(beatAvg));
    drawStatusStrip(SPO2_CARD_X + 1, SPO2_CARD_Y + SPO2_CARD_H - STATUS_STRIP_H - 1,
                    SPO2_CARD_W - 2, STATUS_STRIP_H, spo2StatusColor(ESpO2));

    long currentIR = particleSensor.getIR();
    long currentRed = particleSensor.getRed();
    Serial.print("IR: ");
    Serial.print(currentIR);
    Serial.print(" | RED: ");
    Serial.print(currentRed);
    Serial.print(" | BPM: ");
    if (beatAvg > 0) Serial.print(beatAvg);
    else Serial.print("--");
    Serial.print(" | SpO2: ");
    if (ESpO2 > 80) {
      Serial.print((int)ESpO2);
      Serial.println("%");
    } else {
      Serial.println("--");
    }
    lastUpdate = millis();
  }
}
