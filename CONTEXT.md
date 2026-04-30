# CONTEXT.md

Quick lookup for hardware specs, existing code, and clinical numbers. Keep this file updated as the project evolves.

## Hardware Summary

| Component       | Part            | Role                                          |
|-----------------|-----------------|-----------------------------------------------|
| Microcontroller | LilyGO TTGO T-Display V1.1 | Dual-core, built-in TFT, Wi-Fi          |
| Firmware target | `lilygo-t-display` | PlatformIO environment for the T-Display |
| PPG sensor      | MAX30102        | SpO2 and BPM via IR + Red light; I2C SDA 21, SCL 22 |
| IMU             | MPU6050         | 6-axis accelerometer + gyro for movement      |
| Display         | Integrated 1.14-inch ST7789 TFT | Live SpO2, BPM, movement, PPG strip           |
| Enclosure       | Black nylon, 3D printed | Blocks ambient light, USB charge port |
| Power           | LiPo + 3-pin slide switch | Portable                            |

## Firmware Behaviour Reference

Loop runs continuously. Key signal processing chain in `arduinoCodes.c`:
1. Read raw FIFO from MAX30102
2. SMA smoothing across 5 samples (`SMA_WINDOW`)
3. Median filter across 5 samples (`MEDIAN_SIZE`)
4. Beat detection via `checkForBeat(ir)` from `heartRate.h`
5. BPM averaged over last 15 beats (`RATE_SIZE`)
6. SpO2 derived from R ratio every 200 samples, averaged over last 8 valid values (`SPO2_AVG_COUNT`)
7. SpO2 valid range: 88 to 100. Anything outside is dropped.

Web server (Core 1) exposes:
- `GET /data` returning JSON: `{spo2, bpm, movement, ir, red}`

## Flutter App Behaviour Reference

The Flutter app is the canonical reference for UX patterns in the Flask app.

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

CSV export schema: `Date, Time, SpO2, BPM, IR, RED, Movement`

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

The Flask app should use the same field names so the two clients stay interchangeable.

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
