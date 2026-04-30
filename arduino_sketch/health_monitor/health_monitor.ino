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

void drawPlaceFingerScreen() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_CYAN);
  tft.drawCentreString("HEALTH MONITOR", 120, 10, 2);
  tft.drawLine(0, 30, 240, 30, TFT_DARKGREY);
  tft.setTextSize(1);
  tft.setTextColor(TFT_YELLOW);
  tft.drawCentreString("PLACE FINGER", 120, 60, 4);
}

void drawReadingScreen() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_CYAN);
  tft.drawCentreString("HEALTH MONITOR", 120, 10, 2);
  tft.drawLine(0, 30, 240, 30, TFT_DARKGREY);
}

void drawWifiSplash(const String& line1, const String& line2) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_CYAN);
  tft.drawCentreString("HEALTH MONITOR", 120, 10, 2);
  tft.drawLine(0, 30, 240, 30, TFT_DARKGREY);
  tft.setTextColor(TFT_WHITE);
  tft.drawCentreString(line1, 120, 55, 2);
  tft.setTextColor(TFT_GREEN);
  tft.drawCentreString(line2, 120, 90, 2);
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
      tft.fillCircle(220, 55, 5, TFT_RED);
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
    tft.fillCircle(220, 55, 5, TFT_BLACK);
  }

  // Update display only when finger is present
  static unsigned long lastUpdate = 0;
  if (fingerPresent && millis() - lastUpdate > 300) {
    tft.fillRect(0, 31, 210, 105, TFT_BLACK);
    tft.setTextSize(2);

    tft.setTextColor(TFT_RED);
    tft.setCursor(20, 45);
    tft.print("BPM: ");
    if (beatAvg > 0) tft.print(beatAvg);
    else tft.print("--");

    tft.setTextColor(TFT_GREEN);
    tft.setCursor(20, 90);
    tft.print("SpO2: ");
    if (ESpO2 > 80) {
      tft.print((int)ESpO2);
      tft.print("%");
    } else {
      tft.print("--");
    }

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