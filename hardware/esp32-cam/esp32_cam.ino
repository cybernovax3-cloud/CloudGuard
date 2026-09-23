/**
 * CloudGuard ESP32-CAM Firmware
 * 
 * Functionality:
 * - Camera initialization and JPEG capture
 * - ESP-NOW communication with Main ESP32
 * - Simple HTTP server for image retrieval
 * - Image storage and status reporting
 * - Error handling and recovery
 * 
 * Board: AI-Thinker ESP32-CAM
 * Flash: 4MB
 * PSRAM: Yes (required for image buffer)
 */

#include "esp_camera.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Arduino.h>

// ============================================
// PIN CONFIGURATION (AI-Thinker ESP32-CAM)
// ============================================

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// LED Flash
#define LED_GPIO_NUM      4

// ============================================
// CONFIGURATION
// ============================================

// ESP-NOW MAC Addresses
uint8_t MAIN_ESP32_MAC[6] = {0x08, 0x3A, 0xF2, 0x12, 0x34, 0x56};
uint8_t ESP32_CAM_MAC[6] = {0x08, 0x3A, 0xF2, 0xAB, 0xCD, 0xEF};

// Device ID
const char* DEVICE_ID = "CG-CAM-01";

// Wi-Fi configuration: set locally before deployment; do not commit credentials.
const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
const unsigned long WIFI_TIMEOUT_MS = 15000;
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000;

// HTTP Server
WebServer server(80);
bool http_server_started = false;
unsigned long last_wifi_attempt = 0;

// ============================================
// ESP-NOW MESSAGE STRUCTURE
// ============================================

struct CloudGuardMessage {
  uint8_t message_type;
  uint32_t sequence_number;
  uint32_t timestamp_ms;
  uint8_t command_id;
  uint32_t event_id;
  uint8_t payload_length;
  uint8_t payload[180];
};

#define MESSAGE_TYPE_COMMAND    0x01
#define MESSAGE_TYPE_RESPONSE   0x02

#define CMD_PING                0x10
#define CMD_CAPTURE_IMAGE       0x20
#define CMD_STATUS_REQUEST      0x30
#define CMD_PONG                0x11
#define CMD_IMAGE_READY         0x21
#define CMD_STATUS_RESPONSE     0x31
#define CMD_ERROR               0xFF

#define ERROR_CAMERA_FAILED     0x04
#define ERROR_TIMEOUT           0x03

// ============================================
// GLOBAL STATE
// ============================================

// Image buffer
uint8_t* image_buffer = NULL;
size_t image_size = 0;
uint32_t image_crc32 = 0;
unsigned long last_capture_time = 0;
uint32_t capture_count = 0;

// ESP-NOW state
bool espnow_ready = false;
uint32_t espnow_sequence = 0;
uint32_t last_sequence_received = 0;

// Camera state
bool camera_ready = false;
uint8_t jpeg_quality = 90;
uint8_t frame_size = FRAMESIZE_QVGA;

// ============================================
// SETUP
// ============================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n================================");
  Serial.println("CloudGuard ESP32-CAM Startup");
  Serial.println("================================\n");
  
  // Initialize LED
  pinMode(LED_GPIO_NUM, OUTPUT);
  digitalWrite(LED_GPIO_NUM, LOW);
  
  // Initialize camera
  initCamera();

  // Connect before starting the HTTP server; ESP-NOW remains on WIFI_STA.
  connectToWiFi();
  
  // Initialize ESP-NOW
  initializeESPNOW();
  
  if (WiFi.status() == WL_CONNECTED) {
    startHTTPServer();
  }
  
  Serial.println("\n[STARTUP] System ready!\n");
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {
  maintainWiFiConnection();
  if (WiFi.status() == WL_CONNECTED && !http_server_started) {
    startHTTPServer();
  }
  server.handleClient();
  delay(10);
}

void connectToWiFi() {
  Serial.print("[WiFi] Connecting to SSID '");
  Serial.print(WIFI_SSID);
  Serial.println("'...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  last_wifi_attempt = millis();

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("[WiFi] Connected, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] Connection timeout; will retry");
  }
}

void maintainWiFiConnection() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  if (millis() - last_wifi_attempt < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  Serial.println("[WiFi] Disconnected; reconnecting...");
  connectToWiFi();
}

// ============================================
// CAMERA INITIALIZATION
// ============================================

bool initCamera() {
  Serial.println("[CAMERA] Initializing...");
  
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sda = SIOD_GPIO_NUM;
  config.pin_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 90;
  config.fb_count = 2;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  
  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.print("[CAMERA] Init failed: 0x");
    Serial.println(err, HEX);
    return false;
  }
  
  // Get sensor
  sensor_t * s = esp_camera_sensor_get();
  if (s == NULL) {
    Serial.println("[CAMERA] Sensor not found");
    return false;
  }
  
  // Sensor settings
  s->set_brightness(s, 0);
  s->set_contrast(s, 0);
  s->set_saturation(s, 0);
  s->set_special_effect(s, 0);
  s->set_awb_gain(s, 1);
  s->set_ae_level(s, 0);
  s->set_aec_value(s, 300);
  s->set_gain_ctrl(s, 1);
  s->set_gainceiling(s, GAINCEILING_2X);
  s->set_bpc(s, 1);
  s->set_wpc(s, 1);
  s->set_raw_gma(s, 1);
  s->set_lenc(s, 1);
  
  camera_ready = true;
  Serial.println("[CAMERA] Initialized successfully");
  
  return true;
}

// ============================================
// CAMERA CAPTURE
// ============================================

bool captureImage(uint8_t quality, uint8_t size) {
  if (!camera_ready) {
    Serial.println("[CAMERA] Camera not ready");
    return false;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor == NULL) {
    Serial.println("[CAMERA] Sensor unavailable");
    return false;
  }

  framesize_t requested_frame_size = FRAMESIZE_QVGA;
  switch (size) {
    case FRAMESIZE_QQVGA:
    case FRAMESIZE_QCIF:
    case FRAMESIZE_HQVGA:
    case FRAMESIZE_QVGA:
    case FRAMESIZE_CIF:
    case FRAMESIZE_VGA:
    case FRAMESIZE_SVGA:
      requested_frame_size = static_cast<framesize_t>(size);
      break;
    default:
      Serial.println("[CAMERA] Invalid frame size; using QVGA");
      break;
  }

  // The camera driver uses 10-63, while the CloudGuard command uses 80-95.
  uint8_t requested_quality = 10;
  if (quality >= 80 && quality <= 95) {
    requested_quality = static_cast<uint8_t>(map(quality, 80, 95, 30, 10));
  } else if (quality >= 10 && quality <= 63) {
    requested_quality = quality;
  } else {
    Serial.println("[CAMERA] Invalid JPEG quality; using high quality default");
  }

  sensor->set_framesize(sensor, requested_frame_size);
  sensor->set_quality(sensor, requested_quality);
  frame_size = requested_frame_size;
  jpeg_quality = requested_quality;
  
  Serial.println("[CAMERA] Capturing image...");
  digitalWrite(LED_GPIO_NUM, HIGH); // Flash LED
  
  // Free previous image buffer
  if (image_buffer != NULL) {
    free(image_buffer);
    image_buffer = NULL;
    image_size = 0;
  }
  
  // Capture frame
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAMERA] Capture failed");
    digitalWrite(LED_GPIO_NUM, LOW);
    return false;
  }
  
  // Copy to persistent buffer
  image_buffer = (uint8_t *)malloc(fb->len);
  if (!image_buffer) {
    Serial.println("[CAMERA] Memory allocation failed");
    esp_camera_fb_return(fb);
    digitalWrite(LED_GPIO_NUM, LOW);
    return false;
  }
  
  memcpy(image_buffer, fb->buf, fb->len);
  image_size = fb->len;
  last_capture_time = millis();
  capture_count++;
  
  // Calculate CRC32
  image_crc32 = calculateCRC32(image_buffer, image_size);
  
  esp_camera_fb_return(fb);
  digitalWrite(LED_GPIO_NUM, LOW);
  
  Serial.print("[CAMERA] Captured: ");
  Serial.print(image_size);
  Serial.print(" bytes, CRC32=0x");
  Serial.println(image_crc32, HEX);
  
  return true;
}

// ============================================
// CRC32 CALCULATION
// ============================================

uint32_t calculateCRC32(uint8_t* data, size_t len) {
  uint32_t crc = 0xFFFFFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int j = 0; j < 8; j++) {
      crc = (crc >> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
    }
  }
  return crc ^ 0xFFFFFFFF;
}

// ============================================
// ESP-NOW COMMUNICATION
// ============================================

void initializeESPNOW() {
  Serial.println("[ESPNOW] Initializing...");
  
  WiFi.mode(WIFI_STA);
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESPNOW] Init failed!");
    return;
  }
  
  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataReceived);
  
  // Add Main ESP32 as peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, MAIN_ESP32_MAC, 6);
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

void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  (void)info;
  const uint8_t *incomingData = data;
  if (len < sizeof(CloudGuardMessage)) {
    Serial.println("[ESPNOW] Invalid message size");
    return;
  }
  
  CloudGuardMessage msg;
  memcpy(&msg, incomingData, sizeof(CloudGuardMessage));
  
  // Sequence number check
  if (msg.sequence_number <= last_sequence_received) {
    Serial.println("[ESPNOW] Duplicate message (ignored)");
    return;
  }
  last_sequence_received = msg.sequence_number;
  
  Serial.print("[ESPNOW] RX: cmd=0x");
  Serial.print(msg.command_id, HEX);
  Serial.print(" seq=");
  Serial.println(msg.sequence_number);
  
  switch (msg.command_id) {
    case CMD_PING:
      handlePing(&msg);
      break;
    case CMD_CAPTURE_IMAGE:
      handleCaptureCommand(&msg);
      break;
    case CMD_STATUS_REQUEST:
      handleStatusRequest(&msg);
      break;
    default:
      sendError(&msg, 0x01); // Unknown command
      break;
  }
}

void handlePing(CloudGuardMessage *request) {
  Serial.println("[ESPNOW] PING received, sending PONG...");
  
  CloudGuardMessage response = {};
  response.message_type = MESSAGE_TYPE_RESPONSE;
  response.sequence_number = ++espnow_sequence;
  response.timestamp_ms = millis();
  response.command_id = CMD_PONG;
  response.event_id = request->event_id;
  response.payload_length = 8;
  
  // Payload: uptime (uint32_t) + free heap (uint32_t)
  uint32_t uptime = millis() / 1000;
  uint32_t free_heap = ESP.getFreeHeap();
  
  memcpy(&response.payload[0], &uptime, 4);
  memcpy(&response.payload[4], &free_heap, 4);
  
  if (esp_now_send(MAIN_ESP32_MAC, (uint8_t *)&response, sizeof(CloudGuardMessage)) != ESP_OK) {
    Serial.println("[ESPNOW] PONG send failed");
  }
}

void handleCaptureCommand(CloudGuardMessage *request) {
  Serial.println("[ESPNOW] CAPTURE_IMAGE command received");
  
  if (request->payload_length < 3) {
    sendError(request, 0x02); // Invalid payload
    return;
  }
  
  uint8_t quality = request->payload[0];
  uint8_t size = request->payload[1];
  uint8_t timeout = request->payload[2];
  
  Serial.print("[CAMERA] Quality=");
  Serial.print(quality);
  Serial.print(", Size=");
  Serial.print(size);
  Serial.print(", Timeout=");
  Serial.println(timeout);
  
  // Perform capture
  if (!captureImage(quality, size)) {
    sendError(request, 0x04); // Camera failed
    return;
  }
  
  // Send IMAGE_READY response
  CloudGuardMessage response = {};
  response.message_type = MESSAGE_TYPE_RESPONSE;
  response.sequence_number = ++espnow_sequence;
  response.timestamp_ms = millis();
  response.command_id = CMD_IMAGE_READY;
  response.event_id = request->event_id;
  response.payload_length = 9;
  
  // Payload: status (1 byte) + image_size (4 bytes) + crc32 (4 bytes)
  response.payload[0] = 0; // SUCCESS
  memcpy(&response.payload[1], &image_size, 4);
  memcpy(&response.payload[5], &image_crc32, 4);
  
  Serial.print("[ESPNOW] Sending IMAGE_READY (");
  Serial.print(image_size);
  Serial.println(" bytes)");
  
  if (esp_now_send(MAIN_ESP32_MAC, (uint8_t *)&response, sizeof(CloudGuardMessage)) != ESP_OK) {
    Serial.println("[ESPNOW] IMAGE_READY send failed");
  }
}

void handleStatusRequest(CloudGuardMessage *request) {
  Serial.println("[ESPNOW] STATUS_REQUEST received");
  
  CloudGuardMessage response = {};
  response.message_type = MESSAGE_TYPE_RESPONSE;
  response.sequence_number = ++espnow_sequence;
  response.timestamp_ms = millis();
  response.command_id = CMD_STATUS_RESPONSE;
  response.event_id = request->event_id;
  response.payload_length = 11;
  
  // Payload: camera_ready (1) + captures (2) + last_capture_ms (4) + rssi (1) + error (1) + (2 padding)
  response.payload[0] = camera_ready ? 1 : 0;
  
  uint16_t captures = (uint16_t)min((uint32_t)65535, capture_count);
  memcpy(&response.payload[1], &captures, 2);
  
  uint32_t last_capture_ms = (uint32_t)last_capture_time;
  memcpy(&response.payload[3], &last_capture_ms, 4);
  
  int8_t rssi = WiFi.RSSI();
  memcpy(&response.payload[7], &rssi, 1);
  
  response.payload[8] = 0; // No error
  
  if (esp_now_send(MAIN_ESP32_MAC, (uint8_t *)&response, sizeof(CloudGuardMessage)) != ESP_OK) {
    Serial.println("[ESPNOW] STATUS send failed");
  }
}

void sendError(CloudGuardMessage *request, uint8_t error_code) {
  CloudGuardMessage response = {};
  response.message_type = MESSAGE_TYPE_RESPONSE;
  response.sequence_number = ++espnow_sequence;
  response.timestamp_ms = millis();
  response.command_id = CMD_ERROR;
  response.event_id = request->event_id;
  response.payload_length = 1;
  response.payload[0] = error_code;
  
  Serial.print("[ESPNOW] Sending ERROR: 0x");
  Serial.println(error_code, HEX);
  
  if (esp_now_send(MAIN_ESP32_MAC, (uint8_t *)&response, sizeof(CloudGuardMessage)) != ESP_OK) {
    Serial.println("[ESPNOW] ERROR send failed");
  }
}

// ============================================
// HTTP SERVER FOR IMAGE RETRIEVAL
// ============================================

void startHTTPServer() {
  if (http_server_started) {
    return;
  }

  Serial.println("[HTTP] Starting server on port 80...");
  
  server.on("/api/camera/image", HTTP_GET, handleImageRequest);
  server.on("/api/camera/status", HTTP_GET, handleStatusHTTP);
  server.on("/", HTTP_GET, handleRoot);
  
  server.begin();
  http_server_started = true;
  Serial.println("[HTTP] Server started");
}

void handleRoot() {
  server.send(200, "text/plain", "CloudGuard ESP32-CAM Server");
}

void handleImageRequest() {
  if (image_buffer == NULL || image_size == 0) {
    server.send(404, "text/plain", "No image available");
    return;
  }
  
  Serial.print("[HTTP] Sending image (");
  Serial.print(image_size);
  Serial.println(" bytes)");
  
  server.sendHeader("Content-Type", "image/jpeg");
  server.sendHeader("Content-Length", String(image_size));
  server.send(200, "image/jpeg", "");
  
  server.client().write(image_buffer, image_size);
}

void handleStatusHTTP() {
  String response = "{";
  response += "\"camera_ready\":" + String(camera_ready ? "true" : "false") + ",";
  response += "\"last_capture\":" + String(last_capture_time) + ",";
  response += "\"image_size\":" + String(image_size) + ",";
  response += "\"capture_count\":" + String(capture_count) + ",";
  response += "\"free_heap\":" + String(ESP.getFreeHeap());
  response += "}";
  
  server.send(200, "application/json", response);
}

// ============================================
// SYSTEM DIAGNOSTICS
// ============================================

void printSystemStatus() {
  Serial.println("\n=== ESP32-CAM Status ===");
  Serial.print("Camera: ");
  Serial.println(camera_ready ? "Ready" : "Not Ready");
  Serial.print("ESP-NOW: ");
  Serial.println(espnow_ready ? "Ready" : "Not Ready");
  Serial.print("Last Capture: ");
  Serial.println(last_capture_time);
  Serial.print("Image Size: ");
  Serial.println(image_size);
  Serial.print("Captures: ");
  Serial.println(capture_count);
  Serial.print("Free Heap: ");
  Serial.println(ESP.getFreeHeap());
  Serial.println("========================\n");
}
