# CloudGuard ESP-NOW Testing & Validation Guide

## Overview

This guide provides step-by-step testing procedures to verify each component of the CloudGuard system with ESP-NOW integration.

---

## Test 1: Main ESP32 Sensor Acquisition

### Objective
Verify that the Main ESP32 correctly acquires sensor readings and performs edge processing.

### Prerequisites
- Main ESP32 programmed with `main_esp32.ino`
- Sensors connected and powered
- USB cable connected to computer

### Procedure

**Step 1: Monitor Serial Output**
```bash
# Open Arduino IDE
Tools → Serial Monitor
Select Port: COM3 (or your Main ESP32 port)
Set Baud Rate: 115200
```

**Step 2: Observe Calibration**
You should see:
```
[SENSOR] Calibrating...
[SENSOR] Calibrating...
[SENSOR] Calibration complete
```

**Step 3: Observe Sensor Readings**
Every 30 seconds (or configured interval), you should see:
```
[SENSOR] Water: 45.6 cm, Temp: 25.3 °C, Humidity: 62.5 %
[EDGE] Overall Risk: 23.4 (NORMAL), Flood: NORMAL, Landslide: NORMAL
```

**Step 4: Simulate Water Level Rise**
- Pour water into water level sensor container
- Observe pressure increase
- Edge risk should increase proportionally

**Expected Edge Risk Progression:**
```
Water Level < 100 cm  → Flood Risk: LOW    → NORMAL
Water Level ≥ 100 cm → Flood Risk: HIGH   → WARNING
Water Level ≥ 150 cm → Flood Risk: HIGHER → CRITICAL
```

**Step 5: Simulate Vibration**
- Shake the vibration sensor
- Serial should show: `Vibration: 1` (true)
- Edge risk should increase

**Validation:** ✅ Pass if readings are stable and realistic

---

## Test 2: Wi-Fi Connectivity & Backend Upload

### Objective
Verify that Main ESP32 connects to Wi-Fi and uploads sensor data to the backend.

### Prerequisites
- Main ESP32 with valid Wi-Fi credentials configured
- CloudGuard backend running on network
- Backend IP address known (e.g., 192.168.1.100:5000)

### Procedure

**Step 1: Update Wi-Fi Configuration**

In `main_esp32.ino`, update:
```cpp
const char* WIFI_SSID = "YOUR_HOME_SSID";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
const char* BACKEND_URL = "http://192.168.1.100:5000/api/sensor-data";
```

**Step 2: Recompile and Upload**
```bash
Sketch → Upload
```

**Step 3: Monitor Serial Output**
```
[WiFi] Connecting to SSID 'YOUR_SSID'...
.....
[WiFi] Got IP: 192.168.1.50
[WiFi] Connected!
```

**Step 4: Verify Backend Reception**

Open backend logs (where backend is running):
```bash
cd CloudGuard/backend
python app.py
```

You should see HTTP POST requests:
```
192.168.1.50 - - [08/Sep/2026 12:34:56] "POST /api/sensor-data HTTP/1.1" 200 -
```

And sensor update printout:
```
====================================
CLOUDGUARD SENSOR UPDATE
====================================
Device: CG01
Temperature: 25.3
Humidity: 62.5
...
====================================
```

**Step 5: Verify LED Blinks on Upload**
- Main ESP32 LED should blink briefly when data uploads successfully
- Check frequency matches configured interval (default 30s)

**Step 6: Check Dashboard**
- Open CloudGuard frontend in browser: `http://localhost:5500`
- Navigate to "Live Sensors" section
- Should show device CG01 as "Online"
- Should display latest readings

**Validation:** ✅ Pass if:
- Wi-Fi connects automatically
- LED blinks on upload
- Backend receives POST requests
- Dashboard shows data within 30 seconds

---

## Test 3: Offline Buffering & Retry

### Objective
Verify that Main ESP32 buffers sensor data when Wi-Fi is unavailable and retries on reconnection.

### Prerequisites
- Main ESP32 connected to Wi-Fi and uploading successfully
- Router or Wi-Fi access to control connectivity
- Backend running

### Procedure

**Step 1: Start Baseline Uploads**
```
Observe serial output showing successful uploads every 30s
[UPLOAD] Sensor data sent successfully
```

**Step 2: Simulate Wi-Fi Disconnection**
```bash
# Option A: Disconnect Wi-Fi manually
Click Wi-Fi icon → Select SSID → "Forget"

# Option B: Unplug router temporarily (3 minutes)
```

**Step 3: Observe Buffering**
Serial output should show:
```
[WiFi] Disconnected
[UPLOAD] Wi-Fi not connected, buffering
[BUFFER] Offline reading stored (1 total)
[BUFFER] Offline reading stored (2 total)
[BUFFER] Offline reading stored (3 total)
...
```

**Step 4: Reconnect Wi-Fi**
```bash
# Re-enable Wi-Fi network
```

**Step 5: Observe Retry**
Serial output should show:
```
[WiFi] Connected!
[BUFFER] Attempting to send buffered readings...
[BUFFER] Sent (2 remaining)
[BUFFER] Sent (1 remaining)
[BUFFER] Sent (0 remaining)
[BUFFER] Cleared
```

**Step 6: Verify Backend Reception**
- Check backend logs for multiple POST requests
- All buffered readings should be in database
- Dashboard should show all historical data points

**Validation:** ✅ Pass if:
- Buffer stores up to 100 readings
- All buffered readings are sent on reconnection
- Dashboard shows complete history without gaps

---

## Test 4: ESP-NOW Initialization & Peer Communication

### Objective
Verify that Main ESP32 and ESP32-CAM establish ESP-NOW communication.

### Prerequisites
- Main ESP32 programmed with correct ESP32-CAM MAC address
- ESP32-CAM programmed with correct Main ESP32 MAC address
- Both devices powered up
- Serial monitors open for both

### Procedure

**Step 1: Verify MAC Addresses**

Main ESP32 Serial (115200 baud):
```
[ESPNOW] Initializing...
[ESPNOW] Ready!
```

ESP32-CAM Serial (115200 baud):
```
[ESPNOW] Initializing...
[ESPNOW] Ready!
```

**Step 2: Verify Peer Addition**
Both should complete initialization without errors. If you see:
```
[ESPNOW] Failed to add peer
```

Then MAC addresses are incorrect. Fix in firmware and re-upload.

**Step 3: Test PING Command**

In firmware, add a test that sends PING every 60 seconds by uncommenting in main_esp32.ino:
```cpp
if (espnow_ready && now - last_espnow_ping > 60000) {
  pingCamera();
  last_espnow_ping = now;
}
```

**Main ESP32 Serial:**
```
[ESPNOW] Sending PING...
[ESPNOW] TX: PING to AA:BB:CC:DD:EE:FF (seq=1234)
[ESPNOW] RX: PONG from AA:BB:CC:DD:EE:FF (seq=1234, rssi=-45)
[ESPNOW] Camera is online
```

**ESP32-CAM Serial:**
```
[ESPNOW] RX: cmd=0x10 seq=1234
[ESPNOW] PING received, sending PONG...
[ESPNOW] TX: PONG to AA:BB:CC:DD:EE:FF
```

**Validation:** ✅ Pass if:
- Both devices initialize ESP-NOW without errors
- PING/PONG exchange completes within 2 seconds
- No duplicate messages detected

---

## Test 5: Camera Capture Trigger

### Objective
Verify that critical events trigger camera capture via ESP-NOW.

### Prerequisites
- ESP32-CAM programmed and running
- Main ESP32 programmed
- Both devices on same network (for Wi-Fi)
- Backend running

### Procedure

**Step 1: Simulate Critical Event (Manual Trigger)**

Modify main_esp32.ino to force critical condition:
```cpp
// Temporarily in calculateEdgeRisk():
if (true) { // Force critical
  triggerCameraCapture("Manual test trigger");
}
```

Recompile and upload.

**Step 2: Observe Main ESP32 Serial**
```
[CAMERA] Capture triggered!
[ESPNOW] Sending CAPTURE_IMAGE...
[CAMERA] Sending CAPTURE_IMAGE sent (event=abc123, timeout=5s)
[ESPNOW] TX: cmd=0x20 seq=5678
```

**Step 3: Observe ESP32-CAM Serial**
```
[ESPNOW] RX: cmd=0x20 seq=5678
[ESPNOW] CAPTURE_IMAGE command received
[CAMERA] Quality=90, Size=3, Timeout=5
[CAMERA] Capturing image...
[CAMERA] Captured: 25600 bytes, CRC32=0xabcd1234
[ESPNOW] Sending IMAGE_READY (25600 bytes)
[ESPNOW] TX: cmd=0x21 seq=5679
```

**Step 4: Observe Main ESP32 Response**
```
[ESPNOW] RX: cmd=0x21 seq=5679
[CAMERA] Image ready! Size: 25600 bytes
[CAMERA] Retrieving image from ESP32-CAM...
[CAMERA] Retrieved 25600 bytes
[UPLOAD] Image upload to backend (stub)
```

**Step 5: Verify Backend Camera Event**
```bash
cd CloudGuard/backend
python -c "
from sensor_database import get_latest_camera_event
event = get_latest_camera_event('CG01')
print(event)
"
```

Expected output:
```python
{
  'event_id': 'CG01-20260908123456-a1b2c3d4',
  'device_id': 'CG01',
  'timestamp': '2026-09-08T12:34:56+00:00',
  'trigger_reason': 'Manual test trigger',
  'hazard': 'ENVIRONMENT',
  'status': 'TRIGGERED',
  ...
}
```

**Validation:** ✅ Pass if:
- Event is triggered
- ESP-NOW command sent and received within 5 seconds
- Image ready response contains correct size and CRC32
- Event status updates to CAPTURED

---

## Test 6: Camera Image Upload

### Objective
Verify that captured camera image is uploaded to backend and appears in dashboard.

### Prerequisites
- Test 5 passed (camera capture working)
- Backend running
- Frontend dashboard running

### Procedure

**Step 1: Trigger Capture (from Test 5)**
```
Capture should complete with:
[CAMERA] Retrieving image from ESP32-CAM...
[CAMERA] Retrieved 25600 bytes
```

**Step 2: Monitor Backend for Upload**

In terminal running backend:
```
POST /api/camera/upload
File received: 25600 bytes
Vision analysis: unavailable
Camera event updated
```

**Step 3: Verify Image File Exists**
```bash
# Check camera_uploads directory
ls -la CloudGuard/backend/camera_uploads/
# Should show: latest_image (binary JPEG file)
```

**Step 4: Check Dashboard Camera Section**
- Open dashboard in browser
- Navigate to "Camera Vision" tab
- Should show:
  - Latest capture timestamp
  - Image preview
  - Vision status: UNAVAILABLE (unless model configured)
  - Camera connection: Online

**Step 5: Test Image Download**
```bash
# Try to download the image from backend
curl -O http://192.168.1.100:5000/api/camera/latest?raw=1
file latest_image  # Should detect as JPEG
```

**Validation:** ✅ Pass if:
- Image file is stored on backend
- Dashboard displays image
- Image is valid JPEG format
- File size matches ESP32-CAM report

---

## Test 7: Camera Unavailable Graceful Handling

### Objective
Verify system continues operating if camera is unavailable.

### Prerequisites
- Main ESP32 running
- ESP32-CAM powered down or offline

### Procedure

**Step 1: Power Down ESP32-CAM**
```
Disconnect USB power from ESP32-CAM
```

**Step 2: Observe Main ESP32 Serial**

First PING attempt:
```
[ESPNOW] Sending PING...
[ESPNOW] TX: PING to AA:BB:CC:DD:EE:FF (seq=1234)
[ESPNOW] TIMEOUT waiting for response to CMD_PING
[ESPNOW] Camera is online: false
```

Sensor reading should still complete:
```
[SENSOR] Water: 45.6 cm, Temp: 25.3 °C, Humidity: 62.5 %
[EDGE] Overall Risk: 23.4 (NORMAL), ...
[UPLOAD] Sensor data sent successfully
```

**Step 3: Observe Backend/Dashboard**
- Dashboard should show sensor data as normal
- Camera status should show: "OFFLINE"
- Risk assessment should NOT depend on camera
- System continues normal operation

**Step 4: Power Up ESP32-CAM**
```
Reconnect USB power to ESP32-CAM
Wait 5 seconds for startup
```

**Step 5: Observe Reconnection**
```
[ESPNOW] Sending PING...
[ESPNOW] RX: PONG from AA:BB:CC:DD:EE:FF
[ESPNOW] Camera is online: true
```

Dashboard should update camera status to "ONLINE".

**Validation:** ✅ Pass if:
- System continues without camera
- No crashes or hung processes
- Camera reconnection is automatic
- Risk assessment is unaffected

---

## Test 8: Risk Fusion & Fused Output

### Objective
Verify that current risk, forecast risk, edge risk, and camera evidence are correctly fused.

### Prerequisites
- Main ESP32 uploading sensor data
- At least 10 sensor readings in database (for forecast)
- Backend running with risk fusion enabled

### Procedure

**Step 1: Collect Historical Data**

Let system run for 5+ minutes to accumulate readings:
```bash
# Check database
cd CloudGuard/backend
python -c "
from sensor_database import get_sensor_history
history = get_sensor_history('CG01', 100)
print(f'Total readings: {len(history)}')
"
```

**Step 2: Query Risk Assessment API**
```bash
curl http://192.168.1.100:5000/api/risk-assessment?device_id=CG01 | python -m json.tool
```

Expected response:
```json
{
  "available": true,
  "assessment": {
    "overall_risk": 35.5,
    "current_risk": 25.0,
    "predicted_risk": 45.0,
    "edge_risk": 30.0,
    "vision_risk": null,
    "hazard": "ENVIRONMENT",
    "confidence": 0.75,
    "status": "WATCH",
    "evidence_sources": ["current_sensor", "forecast", "edge"],
    "explanation": "Current sensor risk is 25/100; 6-hour forecast estimates 45/100; Edge evidence: high water level",
    "recommended_action": "Continue monitoring"
  }
}
```

**Step 3: Verify Forecast Calculation**
```bash
curl http://192.168.1.100:5000/api/forecast?device_id=CG01 | python -m json.tool
```

Should show:
- `forecast_available: true` (if 80+ readings)
- `predicted_status: NORMAL|WATCH|WARNING|CRITICAL`
- `confidence: 0.0-1.0`

**Step 4: Trigger Critical Event**

Simulate water level sensor spike:
```
Pour water into water level sensor to trigger high reading
Edge risk should increase to CRITICAL
```

**Step 5: Verify Fused Risk Increases**

Query risk-assessment again:
```bash
curl http://192.168.1.100:5000/api/risk-assessment?device_id=CG01 | python -m json.tool
```

Should now show:
- `overall_risk: 75+` (CRITICAL)
- `edge_risk: 100` (critical water level)
- `status: CRITICAL`
- `recommended_action: Immediate response recommended`

**Step 6: Verify Dashboard Updates**

Dashboard "Risk Intelligence" section should update in real-time showing:
- Overall Risk: 75+
- Status: 🔴 CRITICAL (red indicator)
- Evidence list includes edge decision
- Recommended action displayed

**Validation:** ✅ Pass if:
- Risk fusion combines multiple sources correctly
- Overall risk is max of all components
- Confidence values are reasonable
- Critical status triggers alerts

---

## Test 9: Alert System

### Objective
Verify that critical events generate alerts through all channels.

### Prerequisites
- System at CRITICAL status
- Backend running
- SMS/FCM configured (or gracefully skipped)
- Dashboard open

### Procedure

**Step 1: Trigger Critical Status**
```
Simulate critical water level (from Test 8)
or critical gas sensor reading
```

**Step 2: Check Dashboard Alert**

Navigate to "Alert Center" tab:
```
Should show new CRITICAL alert with:
- Timestamp
- Device: CG01
- Hazard: ENVIRONMENT or specific type
- Severity: CRITICAL (red)
- Message: "Preventive action recommended"
- Status: NOT ACKNOWLEDGED
```

**Step 3: Check Backend Alert Database**
```bash
cd CloudGuard/backend
python -c "
from sensor_database import get_alerts
alerts = get_alerts(10, 'CG01')
print(alerts[-1])  # Last alert
"
```

Output:
```
{
  'alert_id': '...',
  'device_id': 'CG01',
  'severity': 'CRITICAL',
  'hazard': 'ENVIRONMENT',
  'fcm_status': 'NOT_ATTEMPTED|SENT',
  'sms_status': 'NOT_CONFIGURED|SENT|FAILED',
  'camera_status': 'UNAVAILABLE|PENDING|CAPTURED'
}
```

**Step 4: Verify FCM Push (if configured)**

Check Firebase Console or mobile app:
```
Should receive push notification:
"CloudGuard CRITICAL ENVIRONMENT alert for node CG01. Preventive action recommended."
```

**Step 5: Verify SMS (if configured)**

Check phone for SMS from Twilio:
```
CloudGuard CRITICAL ENVIRONMENT alert for node CG01. Preventive action recommended.
```

**Step 6: Verify Cooldown**

Trigger alert again:
```
Should see console message:
"No alert - suppressed by cooldown"
```

Wait ALERT_COOLDOWN_SECONDS (default 300):
```
Next alert should send successfully
```

**Validation:** ✅ Pass if:
- Alert appears in dashboard
- Alert stored in database
- SMS/FCM sent (or gracefully handled if not configured)
- Cooldown prevents alert spam
- Alert history persists

---

## Test 10: End-to-End Workflow

### Objective
Verify complete workflow from sensor to dashboard with all components integrated.

### Prerequisites
- All previous tests passed
- System stable for 10+ minutes

### Procedure

**Step 1: Baseline State**

Dashboard shows:
- CG01 Online
- Temperature: ~25°C
- Humidity: ~60%
- Overall Risk: NORMAL (green)
- Camera: ONLINE (if camera available)

**Step 2: Simulate Flood Scenario**

Main ESP32 (real or simulated):
```
1. Gradually increase water level
2. Add simulated rainfall
3. Add rising rate
```

**Step 3: Observe Progressive Risk Escalation**

```
t=0s:   Risk = NORMAL (0%)
t=30s:  Risk = WATCH (25%)  - water level > 75cm
t=60s:  Risk = WARNING (50%) - water level > 100cm
t=90s:  Risk = CRITICAL (75%) - water level > 150cm or rapid rise
```

**Step 4: Observe Automatic Camera Trigger**

```
Main ESP32 serial: [CAMERA] Capture triggered!
ESP32-CAM serial: [CAMERA] Capturing image...
Dashboard: Camera status changes to "CAPTURED"
```

**Step 5: Observe Alert Cascade**

```
Dashboard: CRITICAL alert banner appears
Database: Alert record created
SMS/FCM: Message sent (if configured)
Risk Assessment: Shows CRITICAL with camera evidence
```

**Step 6: Observe Forecast Warning (if applicable)**

```
If 6-hour forecast predicts continued risk:
Dashboard 6-hour warning section updates
Forecast alert may trigger (WARNING severity)
Evidence sources show: ["current_sensor", "forecast", "edge", "camera"]
```

**Step 7: Recovery**

```
1. Remove simulated water
2. Observe water level decrease
3. Watch risk tier down-graduate: CRITICAL → WARNING → WATCH → NORMAL
4. Camera status updates
5. Alert remains in history but no new alert (cooldown)
```

**Step 8: Dashboard Verification**

Final dashboard should show:
```
Historical view:
- Sensor readings graph showing spike
- Risk timeline showing escalation and recovery
- Camera capture timestamp
- Alert history with all events
- Full risk assessment with recovered status
```

**Validation:** ✅ Pass if:
- Workflow progresses as expected
- No data loss or corruption
- All systems respond consistently
- Dashboard reflects reality in real-time
- Recovery is clean and complete

---

## Test 11: Stress Test (Optional Advanced)

### Objective
Verify system stability under sustained load.

### Prerequisites
- All basic tests passed
- System running stable

### Procedure

**Step 1: Sustained Upload Test**
```bash
# Reduce sensor interval to 5 seconds
const unsigned long SENSOR_INTERVAL_MS = 5000;

# Let system run for 30 minutes
# Observe: No crashes, memory leaks, or failed uploads
```

**Step 2: Repeated Capture Test**
```bash
# Force camera capture every 60 seconds for 1 hour
# Observe: All images retrieved, no corruption, no hangs
```

**Step 3: Network Stress**
```bash
# Disconnect Wi-Fi and reconnect 10 times over 30 minutes
# Observe: All buffered data sent, no data loss
```

**Validation:** ✅ Pass if:
- System runs continuously without crashes
- Memory usage stable
- All uploads and captures succeed
- No buffer overflows

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| No serial output | Wrong baud rate or port | Check Tools → Serial Monitor settings |
| "WiFi not connected" | SSID/password wrong | Update credentials in firmware |
| "ESP-NOW not ready" | MAC address mismatch | Verify MAC with diagnostic sketch |
| "Image upload failed" | Backend unreachable | Check IP, ping backend, check firewall |
| "Duplicate message" | Sequence number bug | Check firmware sequence increment |
| "Camera offline" | ESP-NOW peer missing | Re-add peer with correct MAC |
| "Buffer never clears" | Upload always fails | Check internet and backend status |

---

## Test Summary Checklist

- [ ] Test 1: Sensor Acquisition - PASSED
- [ ] Test 2: Wi-Fi Connectivity - PASSED  
- [ ] Test 3: Offline Buffering - PASSED
- [ ] Test 4: ESP-NOW Communication - PASSED
- [ ] Test 5: Camera Capture Trigger - PASSED
- [ ] Test 6: Camera Upload - PASSED
- [ ] Test 7: Camera Unavailable - PASSED
- [ ] Test 8: Risk Fusion - PASSED
- [ ] Test 9: Alert System - PASSED
- [ ] Test 10: End-to-End Workflow - PASSED
- [ ] Test 11: Stress Test - PASSED (optional)

**All tests passing indicates CloudGuard ESP-NOW integration is production-ready.**
