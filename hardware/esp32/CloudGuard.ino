/*
 * CloudGuard Main ESP32 Firmware
 * 
 * Functionality:
 * - Sensor acquisition (water level, rainfall, temperature, humidity, pressure, soil moisture, vibration, gas sensors)
 * - Edge risk processing (threshold-based, rate-of-change analysis)
 * - ESP-NOW communication with ESP32-CAM
 * - Wi-Fi connectivity and HTTP sensor data upload
 * - Camera command coordination
 * - Offline buffering and retry logic
 * 
 * Board: ESP32 DevKit V1
 * Flash: 4MB
 * PSRAM: Disabled
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <SPIFFS.h>
#include <ArduinoJson.h>
#include <time.h>
#include <vector>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ============================================
// CONFIGURATION
// ============================================

// Wi-Fi Configuration
const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
const char* BACKEND_URL = "http://YOUR_BACKEND_HOST:5000/api/sensor-data";
const char* CAMERA_API_URL = "http://YOUR_CAMERA_HOST/api/camera/image"; // ESP32-CAM HTTP server
const char* CAMERA_UPLOAD_PATH = "/api/camera/upload";
const unsigned long WIFI_TIMEOUT_MS = 15000;
const unsigned long SENSOR_INTERVAL_MS = 30000; // 30 seconds
const unsigned long ESPNOW_RETRY_INTERVAL_MS = 5000;

// Device IDs
const char* DEVICE_ID = "CG01";
const char* DEVICE_NAME = "Main Controller";

// ESP-NOW MAC Addresses (MUST match your hardware)
uint8_t MAIN_ESP32_MAC[6] = {0x08, 0x3A, 0xF2, 0x12, 0x34, 0x56};
uint8_t ESP32_CAM_MAC[6] = {0x08, 0x3A, 0xF2, 0xAB, 0xCD, 0xEF};

// Pin Configuration
#define PIN_SW420              27  // SW-420 digital output
#define PIN_SOIL_MOISTURE      35  // ADC
#define PIN_MQ135              34  // ADC (air quality)
#define PIN_MQ2                32  // ADC (smoke/flammable gas)
#define PIN_RAINFALL           12  // ADC
#define PIN_DHT                4   // DHT22 data
#define PIN_HCSR04_TRIG        18
#define PIN_HCSR04_ECHO        19
#define PIN_OLED_SDA           21
#define PIN_OLED_SCL           22
#define PIN_BMP280_SDA         25
#define PIN_BMP280_SCL         26
#define PIN_BUZZER             13
#define PIN_LED_STATUS         2   // Status LED

#define DHT_TYPE DHT22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDRESS_PRIMARY 0x3C
#define OLED_ADDRESS_SECONDARY 0x3D
#define BMP280_ADDRESS_PRIMARY 0x76
#define BMP280_ADDRESS_SECONDARY 0x77
#define HCSR04_TIMEOUT_US 30000UL
#define HCSR04_MAX_DEPTH_CM 500.0F

// ============================================
// ESP-NOW MESSAGE STRUCTURE
// ============================================

struct CloudGuardMessage {
  uint8_t message_type;      // MESSAGE_TYPE_COMMAND (0x01) or RESPONSE (0x02)
  uint32_t sequence_number;
  uint32_t timestamp_ms;
  uint8_t command_id;
  uint32_t event_id;
  uint8_t payload_length;
  uint8_t payload[180];
};

// Message Types
#define MESSAGE_TYPE_COMMAND    0x01
#define MESSAGE_TYPE_RESPONSE   0x02

// Command IDs
#define CMD_PING                0x10
#define CMD_CAPTURE_IMAGE       0x20
#define CMD_STATUS_REQUEST      0x30
#define CMD_PONG                0x11
#define CMD_IMAGE_READY         0x21
#define CMD_STATUS_RESPONSE     0x31
#define CMD_ERROR               0xFF

// Error Codes
#define ERROR_CAMERA_FAILED     0x04
#define ERROR_TIMEOUT           0x03
#define ERROR_UNKNOWN_COMMAND   0x01

// ============================================
// GLOBAL STATE
// ============================================

// Sensor readings
struct SensorReading {
  float rainfall;
  float rain_sensor_percent;
  float temperature;
  float humidity;
  float pressure;
  float water_level;
  float water_rise;
  float soil_moisture;
  bool vibration;
  float mq2_raw;
  float mq2_change;
  float mq135_raw;
  float mq135_change;
  float latitude;
  float longitude;
} current_reading, previous_reading;

// Edge risk calculation
struct EdgeRisk {
  float flood_risk;
  float landslide_risk;
  float air_gas_risk;
  float overall_risk;
  String flood_status;
  String landslide_status;
  String mq2_status;
  String mq135_status;
  String overall_status;
} edge_risk;

// Camera command state
struct CameraCommand {
  uint32_t event_id;
  uint8_t status;          // 0=IDLE, 1=SENT, 2=WAITING, 3=SUCCESS, 4=FAILED
  unsigned long sent_time;
  uint8_t retry_count;
} camera_command = {0, 0, 0, 0};

// System state
bool wifi_connected = false;
bool espnow_ready = false;
bool camera_online = false;
unsigned long last_sensor_update = 0;
unsigned long last_wifi_check = 0;
unsigned long last_espnow_ping = 0;
uint32_t espnow_sequence = 0;
uint32_t last_sequence_received = 0;

// Offline buffer
std::vector<String> offline_buffer;
const size_t MAX_BUFFER_SIZE = 100;

DHT dht(PIN_DHT, DHT_TYPE);
TwoWire bmpBus(1);
TwoWire sharedSensorBus(0);
Adafruit_BMP280 bmp280(&bmpBus);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &sharedSensorBus, -1);
bool dht_ready = false;
bool bmp280_ready = false;
bool oled_ready = false;
uint8_t oled_address = OLED_ADDRESS_PRIMARY;
bool sensor_reading_valid = false;
unsigned long last_oled_update = 0;
unsigned long last_buzzer_toggle = 0;
bool buzzer_state = false;

// ============================================
// INITIALIZATION
// ============================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n================================");
  Serial.println("CloudGuard Main ESP32 Startup");
  Serial.println("================================\n");
  
  // Initialize LED
  pinMode(PIN_LED_STATUS, OUTPUT);
  digitalWrite(PIN_LED_STATUS, LOW);
  
  // Initialize sensor pins
  pinMode(PIN_SW420, INPUT);
  pinMode(PIN_HCSR04_TRIG, OUTPUT);
  pinMode(PIN_HCSR04_ECHO, INPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_HCSR04_TRIG, LOW);
  digitalWrite(PIN_BUZZER, LOW);
  analogSetAttenuation(ADC_11db); // Full range
  initializeSensors();
  
  // Initialize SPIFFS for offline buffering
  if (!SPIFFS.begin(true)) {
    Serial.println("[ERROR] SPIFFS mount failed!");
  }
  
  // Initialize Wi-Fi
  WiFi.mode(WIFI_STA);
  WiFi.onEvent(onWiFiEvent);
  connectToWiFi();
  
  // Initialize ESP-NOW
  initializeESPNOW();
  
  // Calibrate sensor offsets
  calibrateSensors();
  
  // Start with initial reading
  updateSensorReadings();
  if (sensor_reading_valid) {
    calculateEdgeRisk();
  } else {
    Serial.println("[STARTUP] Waiting for a valid sensor reading");
  }
  
  Serial.println("\n[STARTUP] System ready!\n");
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {
  unsigned long now = millis();
  
  // Periodically check Wi-Fi connection
  if (now - last_wifi_check > 30000) {
    checkWiFiConnection();
    last_wifi_check = now;
  }
  
  // Periodically ping ESP32-CAM to check connectivity
  if (espnow_ready && now - last_espnow_ping > 60000) {
    pingCamera();
    last_espnow_ping = now;
  }
  
  // Acquire and upload sensor data
  if (now - last_sensor_update > SENSOR_INTERVAL_MS) {
    updateSensorReadings();
    if (sensor_reading_valid) {
      calculateEdgeRisk();
      uploadSensorData();
    } else {
      Serial.println("[SENSOR] Invalid live reading; upload skipped");
    }
    last_sensor_update = now;
  }

  updateBuzzer(now);
  if (now - last_oled_update >= 1000) {
    updateOLED();
    last_oled_update = now;
  }
  
  // Check camera command status
  if (camera_command.status == 2) { // WAITING
    if (now - camera_command.sent_time > 5000) {
      if (camera_command.retry_count < 2) {
        camera_command.retry_count++;
        sendCameraCommand();
      } else {
        Serial.println("[CAMERA] Capture failed - timeout");
        camera_command.status = 4; // FAILED
      }
    }
  }
  
  // Retry failed image upload
  if (camera_command.status == 3) { // SUCCESS - try to upload
    retrieveAndUploadCameraImage();
  }
  
  delay(100);
}

// ============================================
// SENSOR ACQUISITION
// ============================================

void initializeSensors() {
  dht.begin();
  dht_ready = true;

  bmpBus.begin(PIN_BMP280_SDA, PIN_BMP280_SCL, 400000);
  bmp280_ready = bmp280.begin(BMP280_ADDRESS_PRIMARY);
  if (!bmp280_ready) {
    bmp280_ready = bmp280.begin(BMP280_ADDRESS_SECONDARY);
  }

  selectSharedSensorBus(PIN_OLED_SDA, PIN_OLED_SCL);
  oled_address = detectOLEDAddress();
  oled_ready = oled_address != 0 && display.begin(SSD1306_SWITCHCAPVCC, oled_address, true, false);
  if (oled_ready) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("CloudGuard");
    display.println("Sensors starting...");
    display.display();
  }

  Serial.print("[SENSOR] DHT22: ");
  Serial.println(dht_ready ? "ready" : "unavailable");
  Serial.print("[SENSOR] BMP280: ");
  Serial.println(bmp280_ready ? "ready" : "unavailable");
  Serial.print("[SENSOR] OLED SSD1306: ");
  Serial.println(oled_ready ? "ready" : "unavailable");
}

void selectSharedSensorBus(int sda, int scl) {
  sharedSensorBus.end();
  sharedSensorBus.begin(sda, scl, 400000);
}

uint8_t detectOLEDAddress() {
  for (uint8_t address : {OLED_ADDRESS_PRIMARY, OLED_ADDRESS_SECONDARY}) {
    sharedSensorBus.beginTransmission(address);
    if (sharedSensorBus.endTransmission() == 0) {
      return address;
    }
  }
  return 0;
}

void calibrateSensors() {
  Serial.println("[SENSOR] Calibrating...");
  
  // Read initial values for baseline
  for (int i = 0; i < 10; i++) {
    updateSensorReadings();
    delay(100);
  }
  
  previous_reading = current_reading;
  Serial.println("[SENSOR] Calibration complete");
}

void updateSensorReadings() {
  // Store previous readings for rate-of-change
  previous_reading = current_reading;
  
  // ADC readings (0-4095 for 12-bit, 0-3.3V)
  int raw_rainfall = analogRead(PIN_RAINFALL);
  int raw_soil = analogRead(PIN_SOIL_MOISTURE);
  int raw_mq2 = analogRead(PIN_MQ2);
  int raw_mq135 = analogRead(PIN_MQ135);

  float water_level = readWaterLevelCm();
  if (isnan(water_level) || !isfinite(water_level)) {
    Serial.println("[SENSOR] HC-SR04 invalid - continuing with previous/fallback water level");
    water_level = previous_reading.water_level > 0.0F
        ? previous_reading.water_level
        : 0.0F;
    Serial.print("[SENSOR] Using fallback water level: ");
    Serial.println(water_level);
  }
  current_reading.water_level = water_level;
  
  // Rainfall (simulated - would come from rainfall sensor)
  // This is a placeholder - real implementation would integrate actual rainfall sensor data
  current_reading.rainfall = (raw_rainfall / 4095.0) * 100.0;
  current_reading.rain_sensor_percent = (raw_rainfall / 4095.0) * 100.0;
  
  // Soil moisture (0-100%)
  current_reading.soil_moisture = (raw_soil / 4095.0) * 100.0;
  
  sensor_reading_valid = false;
  if (!dht_ready || !bmp280_ready) {
    Serial.print("[SENSOR] Required sensor is not initialized: DHT22=");
    Serial.print(dht_ready ? "ready" : "unavailable");
    Serial.print(" BMP280=");
    Serial.print(bmp280_ready ? "ready" : "unavailable");
    return;
  }

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  float pressure = bmp280.readPressure() / 100.0F;

  if (isnan(temperature) || isnan(humidity) || isnan(pressure) ||
      !isfinite(temperature) || !isfinite(humidity) || !isfinite(pressure)) {
    Serial.print("[SENSOR] Invalid required reading: temperature=");
    Serial.print(isfinite(temperature) ? "valid" : "invalid");
    Serial.print(" humidity=");
    Serial.print(isfinite(humidity) ? "valid" : "invalid");
    Serial.print(" pressure=");
    Serial.println(isfinite(pressure) ? "valid" : "invalid");
    return;
  }

  current_reading.temperature = temperature;
  current_reading.humidity = constrain(humidity, 0.0F, 100.0F);
  current_reading.pressure = pressure;

  // Water rise (rate of change in cm/s)
  if (previous_reading.water_level > 0) {
    current_reading.water_rise = current_reading.water_level - previous_reading.water_level;
  } else {
    current_reading.water_rise = 0;
  }
  
  // Vibration (SW-420 digital input)
  current_reading.vibration = digitalRead(PIN_SW420) == HIGH;
  
  // Gas sensors (MQ-2 raw ADC value)
  current_reading.mq2_raw = (raw_mq2 / 4095.0) * 1024.0;
  current_reading.mq2_change = current_reading.mq2_raw - (previous_reading.mq2_raw > 0 ? previous_reading.mq2_raw : current_reading.mq2_raw);
  
  // Gas sensors (MQ-135 raw ADC value)
  current_reading.mq135_raw = (raw_mq135 / 4095.0) * 1024.0;
  current_reading.mq135_change = current_reading.mq135_raw - (previous_reading.mq135_raw > 0 ? previous_reading.mq135_raw : current_reading.mq135_raw);
  
  Serial.print("[SENSOR] Water: ");
  Serial.print(current_reading.water_level);
  Serial.print(" cm, Temp: ");
  Serial.print(current_reading.temperature);
  Serial.print(" °C, Humidity: ");
  Serial.print(current_reading.humidity);
  Serial.println(" %");
  sensor_reading_valid = true;
}

float readWaterLevelCm() {
  digitalWrite(PIN_HCSR04_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_HCSR04_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_HCSR04_TRIG, LOW);

  unsigned long duration = pulseIn(PIN_HCSR04_ECHO, HIGH, HCSR04_TIMEOUT_US);
  if (duration == 0) {
    return NAN;
  }

  float distance_cm = duration * 0.0343F / 2.0F;
  if (distance_cm <= 0.0F || distance_cm > HCSR04_MAX_DEPTH_CM) {
    return NAN;
  }

  return constrain(HCSR04_MAX_DEPTH_CM - distance_cm, 0.0F, HCSR04_MAX_DEPTH_CM);
}

// ============================================
// EDGE RISK CALCULATION
// ============================================

String getStatus(float score) {
  if (score >= 75.0) return "CRITICAL";
  if (score >= 50.0) return "WARNING";
  if (score >= 25.0) return "WATCH";
  return "NORMAL";
}

void calculateEdgeRisk() {
  float score = 0.0;
  
  // Flood risk
  float flood_score = 0.0;
  if (current_reading.water_level >= 100) {
    flood_score += 55;
  }
  if (current_reading.water_rise >= 5) {
    flood_score += 35;
  }
  if (current_reading.rainfall >= 75) {
    flood_score += 25;
  }
  flood_score = constrain(flood_score, 0.0, 100.0);
  edge_risk.flood_risk = flood_score;
  edge_risk.flood_status = getStatus(flood_score);
  
  // Landslide risk
  float landslide_score = 0.0;
  if (current_reading.vibration) {
    landslide_score += 25;
  }
  if (current_reading.soil_moisture >= 80) {
    landslide_score += 20;
  }
  landslide_score = constrain(landslide_score, 0.0, 100.0);
  edge_risk.landslide_risk = landslide_score;
  edge_risk.landslide_status = getStatus(landslide_score);
  
  // Air/Gas risk
  float gas_score = 0.0;
  if (current_reading.mq2_change >= 50) {
    gas_score += 30;
  }
  if (current_reading.mq135_raw >= 500) {
    gas_score += 20;
  }
  gas_score = constrain(gas_score, 0.0, 100.0);
  edge_risk.air_gas_risk = gas_score;
  edge_risk.mq2_status = getStatus(current_reading.mq2_raw > 500 ? 50 : 0);
  edge_risk.mq135_status = getStatus(current_reading.mq135_raw > 500 ? 50 : 0);
  
  // Overall risk
  edge_risk.overall_risk = max({flood_score, landslide_score, gas_score});
  edge_risk.overall_status = getStatus(edge_risk.overall_risk);
  
  Serial.print("[EDGE] Overall Risk: ");
  Serial.print(edge_risk.overall_risk);
  Serial.print(" (");
  Serial.print(edge_risk.overall_status);
  Serial.print("), Flood: ");
  Serial.print(edge_risk.flood_status);
  Serial.print(", Landslide: ");
  Serial.print(edge_risk.landslide_status);
  Serial.println();
  
  // Trigger camera if critical
  if (edge_risk.overall_status == "CRITICAL") {
    triggerCameraCapture("Confirmed critical event");
  }
}

void updateBuzzer(unsigned long now) {
  unsigned long interval = 0;
  if (edge_risk.overall_status == "CRITICAL") {
    interval = 150;
  } else if (edge_risk.overall_status == "WARNING") {
    interval = 500;
  } else {
    if (buzzer_state) {
      buzzer_state = false;
      digitalWrite(PIN_BUZZER, LOW);
    }
    return;
  }

  if (now - last_buzzer_toggle >= interval) {
    last_buzzer_toggle = now;
    buzzer_state = !buzzer_state;
    digitalWrite(PIN_BUZZER, buzzer_state ? HIGH : LOW);
  }
}

void updateOLED() {
  if (!oled_ready) {
    return;
  }

  selectSharedSensorBus(PIN_OLED_SDA, PIN_OLED_SCL);
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("CloudGuard");
  display.print("Risk: ");
  display.print(edge_risk.overall_risk, 0);
  display.print(" ");
  display.println(edge_risk.overall_status);
  display.print("Water: ");
  display.print(current_reading.water_level, 1);
  display.println(" cm");
  display.print("Temp: ");
  display.print(current_reading.temperature, 1);
  display.println(" C");
  display.print("WiFi: ");
  display.println(wifi_connected ? "online" : "offline");
  display.display();
}

// ============================================
// SENSOR DATA UPLOAD
// ============================================

void uploadSensorData() {
  if (!wifi_connected) {
    Serial.println("[UPLOAD] Wi-Fi not connected, buffering");
    bufferSensorReading();
    return;
  }
  
  // Create JSON payload
  StaticJsonDocument<1024> doc;
  doc["device_id"] = DEVICE_ID;
  doc["rainfall"] = current_reading.rainfall;
  doc["rain_sensor_percent"] = current_reading.rain_sensor_percent;
  doc["temperature"] = current_reading.temperature;
  doc["humidity"] = current_reading.humidity;
  doc["pressure"] = current_reading.pressure;
  doc["water_level"] = current_reading.water_level;
  doc["water_rise"] = current_reading.water_rise;
  doc["soil_moisture"] = current_reading.soil_moisture;
  doc["vibration"] = current_reading.vibration;
  doc["mq2_raw"] = current_reading.mq2_raw;
  doc["mq2_change"] = current_reading.mq2_change;
  doc["mq135_raw"] = current_reading.mq135_raw;
  doc["mq135_change"] = current_reading.mq135_change;
  // Edge risk from local processing
  doc["flood_risk"] = edge_risk.flood_risk;
  doc["landslide_risk"] = edge_risk.landslide_risk;
  doc["air_gas_risk"] = edge_risk.air_gas_risk;
  doc["overall_risk"] = edge_risk.overall_risk;
  doc["flood_status"] = edge_risk.flood_status;
  doc["landslide_status"] = edge_risk.landslide_status;
  doc["mq2_status"] = edge_risk.mq2_status;
  doc["mq135_status"] = edge_risk.mq135_status;
  doc["overall_status"] = edge_risk.overall_status;
  
  String payload;
  serializeJson(doc, payload);
  
  // Send HTTP POST
  HTTPClient http;
  http.begin(BACKEND_URL);
  http.addHeader("Content-Type", "application/json");

  Serial.print("[UPLOAD] URL: ");
  Serial.println(BACKEND_URL);
  Serial.print("[UPLOAD] ESP32 IP: ");
  Serial.println(WiFi.localIP());
  Serial.println("[UPLOAD] Payload:");
  Serial.println(payload);
  
  int response = http.POST(payload);
  String response_body = http.getString();

  Serial.print("[UPLOAD] HTTP response: ");
  Serial.println(response);
  Serial.println("[UPLOAD] Response body:");
  Serial.println(response_body);
  if (response < 0) {
    Serial.print("[UPLOAD] HTTP error: ");
    Serial.println(http.errorToString(response));
  }
  
  if (response == 200) {
    Serial.println("[UPLOAD] Sensor data sent successfully");
    digitalWrite(PIN_LED_STATUS, HIGH);
    delay(100);
    digitalWrite(PIN_LED_STATUS, LOW);
    
    // Clear offline buffer on successful upload
    clearOfflineBuffer();
  } else {
    Serial.print("[UPLOAD] Failed (HTTP ");
    Serial.print(response);
    Serial.println("), buffering");
    bufferSensorReading();
  }
  
  http.end();
}

void bufferSensorReading() {
  if (offline_buffer.size() >= MAX_BUFFER_SIZE) {
    offline_buffer.erase(offline_buffer.begin()); // Remove oldest
  }
  
  StaticJsonDocument<1024> doc;
  doc["device_id"] = DEVICE_ID;
  doc["rainfall"] = current_reading.rainfall;
  doc["rain_sensor_percent"] = current_reading.rain_sensor_percent;
  doc["temperature"] = current_reading.temperature;
  doc["humidity"] = current_reading.humidity;
  doc["pressure"] = current_reading.pressure;
  doc["water_level"] = current_reading.water_level;
  doc["water_rise"] = current_reading.water_rise;
  doc["soil_moisture"] = current_reading.soil_moisture;
  doc["vibration"] = current_reading.vibration;
  doc["mq2_raw"] = current_reading.mq2_raw;
  doc["mq2_change"] = current_reading.mq2_change;
  doc["mq135_raw"] = current_reading.mq135_raw;
  doc["mq135_change"] = current_reading.mq135_change;
  doc["flood_risk"] = edge_risk.flood_risk;
  doc["landslide_risk"] = edge_risk.landslide_risk;
  doc["air_gas_risk"] = edge_risk.air_gas_risk;
  doc["overall_risk"] = edge_risk.overall_risk;
  doc["flood_status"] = edge_risk.flood_status;
  doc["landslide_status"] = edge_risk.landslide_status;
  doc["mq2_status"] = edge_risk.mq2_status;
  doc["mq135_status"] = edge_risk.mq135_status;
  doc["overall_status"] = edge_risk.overall_status;
  
  String payload;
  serializeJson(doc, payload);
  offline_buffer.push_back(payload);
  
  Serial.print("[BUFFER] Offline reading stored (");
  Serial.print(offline_buffer.size());
  Serial.println(" total)");
}

void clearOfflineBuffer() {
  offline_buffer.clear();
  Serial.println("[BUFFER] Cleared");
}

void retryOfflineBuffer() {
  if (offline_buffer.empty() || !wifi_connected) return;
  
  Serial.println("[BUFFER] Attempting to send buffered readings...");
  
  HTTPClient http;
  for (size_t i = 0; i < offline_buffer.size(); ) {
    http.begin(BACKEND_URL);
    http.addHeader("Content-Type", "application/json");
    
    int response = http.POST(offline_buffer[i]);
    http.end();
    
    if (response == 200) {
      offline_buffer.erase(offline_buffer.begin() + i);
      Serial.print("[BUFFER] Sent (");
      Serial.print(offline_buffer.size());
      Serial.println(" remaining)");
    } else {
      i++;
    }
  }
}

// ============================================
// WIFI CONNECTIVITY
// ============================================

void onWiFiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_CONNECTED:
      Serial.println("[WiFi] Connected to SSID");
      break;
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.print("[WiFi] Got IP: ");
      Serial.println(WiFi.localIP());
      wifi_connected = true;
      retryOfflineBuffer();
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.println("[WiFi] Disconnected");
      wifi_connected = false;
      break;
    default:
      break;
  }
}

void connectToWiFi() {
  Serial.print("[WiFi] Connecting to SSID '");
  Serial.print(WIFI_SSID);
  Serial.println("'...");
  
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(500);
    Serial.print(".");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected!");
    wifi_connected = true;
  } else {
    Serial.println("\n[WiFi] Failed to connect (will retry later)");
    wifi_connected = false;
  }
}

void checkWiFiConnection() {
  if (WiFi.status() != WL_CONNECTED) {
    wifi_connected = false;
    Serial.println("[WiFi] Disconnected, attempting reconnect...");
    WiFi.reconnect();
  }
}

// ============================================
// ESP-NOW COMMUNICATION
// ============================================

void initializeESPNOW() {
  Serial.println("[ESPNOW] Initializing...");
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESPNOW] Init failed!");
    return;
  }
  
  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataReceived);
  
  // Add ESP32-CAM as peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, ESP32_CAM_MAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("[ESPNOW] Failed to add peer");
    return;
  }
  
  espnow_ready = true;
  Serial.println("[ESPNOW] Ready!");
}

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  (void)info;
  Serial.print("[ESPNOW] Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  (void)info;
  if (len < sizeof(CloudGuardMessage)) {
    Serial.println("[ESPNOW] Invalid message size");
    return;
  }
  
  CloudGuardMessage msg;
  memcpy(&msg, incomingData, sizeof(CloudGuardMessage));
  
  // Sequence number check for duplicate prevention
  if (msg.sequence_number <= last_sequence_received) {
    Serial.println("[ESPNOW] Duplicate message (ignored)");
    return;
  }
  last_sequence_received = msg.sequence_number;
  
  Serial.print("[ESPNOW] RX: cmd=0x");
  Serial.print(msg.command_id, HEX);
  Serial.print(" seq=");
  Serial.println(msg.sequence_number);
  
  if (msg.command_id == CMD_IMAGE_READY) {
    handleImageReady(&msg);
  } else if (msg.command_id == CMD_PONG) {
    Serial.println("[ESPNOW] Camera is online");
    camera_online = true;
  } else if (msg.command_id == CMD_ERROR) {
    Serial.print("[ESPNOW] Camera error code: 0x");
    Serial.println(msg.payload[0], HEX);
    camera_command.status = 4; // FAILED
  }
}

void pingCamera() {
  if (!espnow_ready) return;
  
  Serial.println("[ESPNOW] Sending PING...");
  
  CloudGuardMessage msg = {};
  msg.message_type = MESSAGE_TYPE_COMMAND;
  msg.sequence_number = ++espnow_sequence;
  msg.timestamp_ms = millis();
  msg.command_id = CMD_PING;
  msg.event_id = millis();
  msg.payload_length = 0;
  
  if (esp_now_send(ESP32_CAM_MAC, (uint8_t *)&msg, sizeof(CloudGuardMessage)) != ESP_OK) {
    Serial.println("[ESPNOW] PING send failed");
    camera_online = false;
  }
}

void triggerCameraCapture(const char* reason) {
  if (camera_command.status != 0) {
    Serial.println("[CAMERA] Command already in progress");
    return;
  }
  
  Serial.println("[CAMERA] Capture triggered!");
  camera_command.event_id = millis();
  camera_command.status = 1; // SENT
  camera_command.sent_time = millis();
  camera_command.retry_count = 0;
  
  sendCameraCommand();
}

void sendCameraCommand() {
  if (!espnow_ready) {
    Serial.println("[CAMERA] ESP-NOW not ready");
    camera_command.status = 4; // FAILED
    return;
  }
  
  CloudGuardMessage msg = {};
  msg.message_type = MESSAGE_TYPE_COMMAND;
  msg.sequence_number = ++espnow_sequence;
  msg.timestamp_ms = millis();
  msg.command_id = CMD_CAPTURE_IMAGE;
  msg.event_id = camera_command.event_id;
  msg.payload_length = 3;
  msg.payload[0] = 90;      // JPEG quality
  msg.payload[1] = 3;       // Frame size QVGA (320x240)
  msg.payload[2] = 5;       // Timeout
  
  Serial.println("[CAMERA] Sending CAPTURE_IMAGE...");
  
  if (esp_now_send(ESP32_CAM_MAC, (uint8_t *)&msg, sizeof(CloudGuardMessage)) != ESP_OK) {
    Serial.println("[CAMERA] CAPTURE send failed");
    camera_command.status = 4; // FAILED
  } else {
    camera_command.status = 2; // WAITING
  }
}

void handleImageReady(CloudGuardMessage *msg) {
  uint8_t status = msg->payload[0];
  uint32_t image_size = *(uint32_t *)&msg->payload[1];
  
  Serial.print("[CAMERA] Image ready! Size: ");
  Serial.print(image_size);
  Serial.println(" bytes");
  
  if (status == 0) {
    camera_command.status = 3; // SUCCESS
  } else {
    Serial.println("[CAMERA] Camera report status: FAILED");
    camera_command.status = 4;
  }
}

void retrieveAndUploadCameraImage() {
  if (!wifi_connected) {
    Serial.println("[CAMERA] Cannot retrieve image - no WiFi");
    camera_command.status = 0;
    return;
  }
  
  Serial.println("[CAMERA] Retrieving image from ESP32-CAM...");
  
  HTTPClient http;
  http.begin(CAMERA_API_URL);
  int response = http.GET();
  
  if (response == 200) {
    Serial.print("[CAMERA] Retrieved ");
    Serial.print(http.getSize());
    Serial.println(" bytes");
    
    // Upload to backend
    uploadImageToBackend(http.getStream(), http.getSize());
  } else {
    Serial.print("[CAMERA] Retrieval failed (HTTP ");
    Serial.print(response);
    Serial.println(")");
  }
  
  http.end();
  camera_command.status = 0; // Reset
}

void uploadImageToBackend(NetworkClient &stream, size_t image_size) {
  const size_t MAX_CAMERA_UPLOAD_BYTES = 5 * 1024 * 1024;
  const char* boundary = "----CloudGuardCameraBoundary";
  const String device_part = String("--") + boundary +
      "\r\nContent-Disposition: form-data; name=\"device_id\"\r\n\r\n" +
      DEVICE_ID + "\r\n";
  const String image_part = String("--") + boundary +
      "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n" +
      "Content-Type: image/jpeg\r\n\r\n";
  const String closing_part = String("\r\n--") + boundary + "--\r\n";

  if (image_size == 0 || image_size > MAX_CAMERA_UPLOAD_BYTES) {
    Serial.println("[UPLOAD] Invalid image size; upload skipped");
    return;
  }

  const size_t content_length = device_part.length() + image_part.length() +
      image_size + closing_part.length();
  NetworkClient backend;
  if (!backend.connect("192.168.1.9", 5000)) {
    Serial.println("[UPLOAD] Backend connection failed");
    return;
  }

  backend.print("POST ");
  backend.print(CAMERA_UPLOAD_PATH);
  backend.print(" HTTP/1.1\r\n");
  backend.print("Host: 192.168.1.9:5000\r\n");
  backend.print("Content-Type: multipart/form-data; boundary=");
  backend.print(boundary);
  backend.print("\r\nContent-Length: ");
  backend.print(content_length);
  backend.print("\r\nConnection: close\r\n\r\n");
  backend.print(device_part);
  backend.print(image_part);

  uint8_t buffer[1024];
  size_t remaining = image_size;
  while (remaining > 0) {
    if (!stream.available()) {
      if (!stream.connected()) {
        Serial.println("[UPLOAD] Camera stream ended before image completed");
        backend.stop();
        return;
      }
      delay(1);
      continue;
    }

    size_t requested = min(sizeof(buffer), remaining);
    int received = stream.read(buffer, requested);
    if (received <= 0) {
      Serial.println("[UPLOAD] Camera stream read failed");
      backend.stop();
      return;
    }

    size_t written = 0;
    while (written < static_cast<size_t>(received)) {
      size_t sent = backend.write(buffer + written, received - written);
      if (sent == 0) {
        Serial.println("[UPLOAD] Backend write failed");
        backend.stop();
        return;
      }
      written += sent;
    }
    remaining -= static_cast<size_t>(received);
  }

  backend.print(closing_part);
  backend.flush();
  backend.setTimeout(5000);
  String status_line = backend.readStringUntil('\n');
  Serial.print("[UPLOAD] Backend response: ");
  Serial.println(status_line);
  backend.stop();
}

// ============================================
// SYSTEM DIAGNOSTICS
// ============================================

void printSystemStatus() {
  Serial.println("\n=== CloudGuard System Status ===");
  Serial.print("Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.print("WiFi: ");
  Serial.println(wifi_connected ? "Connected" : "Offline");
  Serial.print("ESP-NOW: ");
  Serial.println(espnow_ready ? "Ready" : "Not Ready");
  Serial.print("Camera: ");
  Serial.println(camera_online ? "Online" : "Offline");
  Serial.print("Edge Risk: ");
  Serial.print(edge_risk.overall_risk);
  Serial.print(" (");
  Serial.print(edge_risk.overall_status);
  Serial.println(")");
  Serial.print("Offline Buffer: ");
  Serial.print(offline_buffer.size());
  Serial.println(" readings");
  Serial.println("================================\n");
}
