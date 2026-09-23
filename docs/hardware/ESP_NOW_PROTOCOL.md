# CloudGuard ESP-NOW Protocol Specification

## Overview

ESP-NOW provides local wireless communication between the main ESP32 and ESP32-CAM with low latency and minimal overhead. This protocol defines the message structure, commands, responses, and state management.

---

## Message Structure

### ESP-NOW Packet Format

```c
struct CloudGuardMessage {
  uint8_t message_type;      // MESSAGE_TYPE_COMMAND or MESSAGE_TYPE_RESPONSE
  uint32_t sequence_number;  // Incremented per message for duplicate detection
  uint32_t timestamp_ms;     // Milliseconds since boot
  uint8_t command_id;        // Command type (PING, CAPTURE, STATUS, etc.)
  uint32_t event_id;         // Unique event identifier
  uint8_t payload_length;    // Number of payload bytes (0-180)
  uint8_t payload[180];      // Command-specific data
};
```

**Total size: 198 bytes (within ESP-NOW 250-byte limit)**

### Message Types

```c
#define MESSAGE_TYPE_COMMAND    0x01
#define MESSAGE_TYPE_RESPONSE   0x02
#define MESSAGE_TYPE_ACK        0x03
```

### Command IDs

```c
// Main ESP32 → ESP32-CAM
#define CMD_PING                0x10  // Ping/connectivity check
#define CMD_CAPTURE_IMAGE       0x20  // Capture JPEG image
#define CMD_STATUS_REQUEST      0x30  // Request camera status
#define CMD_RESET               0x40  // Reset camera

// ESP32-CAM → Main ESP32
#define CMD_PONG                0x11  // Response to ping
#define CMD_IMAGE_READY         0x21  // Image captured, ready for retrieval
#define CMD_STATUS_RESPONSE     0x31  // Camera status
#define CMD_ERROR               0xFF  // Error indication
```

---

## Command Sequences

### 1. PING / PONG (Connectivity Check)

**Request (Main ESP32 → ESP32-CAM):**
```
message_type: MESSAGE_TYPE_COMMAND
command_id:   CMD_PING
event_id:     event_counter
payload:      (empty)
```

**Response (ESP32-CAM → Main ESP32):**
```
message_type: MESSAGE_TYPE_RESPONSE
command_id:   CMD_PONG
event_id:     matching request event_id
payload:      
  - uptime_seconds (uint32_t)
  - free_heap (uint32_t)
```

**Timeout:** 2000ms  
**Retry:** 3 attempts

---

### 2. CAPTURE_IMAGE (Camera Trigger)

**Request (Main ESP32 → ESP32-CAM):**
```
message_type: MESSAGE_TYPE_COMMAND
command_id:   CMD_CAPTURE_IMAGE
event_id:     backend event_id (from /api/camera/trigger)
payload:
  - jpeg_quality (uint8_t, 80-95)
  - frame_size (uint8_t) // See FRAMESIZE_*
  - timeout_seconds (uint8_t)
```

**Response (ESP32-CAM → Main ESP32):**
```
message_type: MESSAGE_TYPE_RESPONSE
command_id:   CMD_IMAGE_READY
event_id:     matching request event_id
payload:
  - status (uint8_t) // 0=SUCCESS, 1=FAILED, 2=TIMEOUT
  - image_size (uint32_t) // Total JPEG size
  - image_crc32 (uint32_t) // CRC32 of JPEG for integrity
  - timestamp (uint32_t) // Capture time in milliseconds
```

**Timeout:** 5000ms  
**Retry:** 2 attempts

**Frame Size Enum:**
```
FRAMESIZE_QQVGA = 0,  // 160x120
FRAMESIZE_QCIF  = 1,  // 176x144
FRAMESIZE_HQVGA = 2,  // 240x176
FRAMESIZE_QVGA  = 3,  // 320x240
FRAMESIZE_CIF   = 4,  // 400x296
FRAMESIZE_VGA   = 5,  // 640x480
FRAMESIZE_SVGA  = 6,  // 800x600
```

---

### 3. STATUS_REQUEST / STATUS_RESPONSE

**Request (Main ESP32 → ESP32-CAM):**
```
message_type: MESSAGE_TYPE_COMMAND
command_id:   CMD_STATUS_REQUEST
event_id:     status_check_id
payload:      (empty)
```

**Response (ESP32-CAM → Main ESP32):**
```
message_type: MESSAGE_TYPE_RESPONSE
command_id:   CMD_STATUS_RESPONSE
event_id:     matching request event_id
payload:
  - camera_ready (uint8_t) // 0=not ready, 1=ready
  - images_captured (uint16_t) // Total since boot
  - last_capture_ms (uint32_t) // Time of last capture
  - wifi_strength (int8_t) // RSSI in dBm
  - system_error (uint8_t) // 0=none, other=error code
```

**Timeout:** 2000ms  
**Retry:** 3 attempts

---

### 4. ERROR Response

**Response (Any → Any):**
```
message_type: MESSAGE_TYPE_RESPONSE
command_id:   CMD_ERROR
event_id:     related command event_id
payload:
  - error_code (uint8_t) // See ERROR_* codes
  - error_detail (uint16_t) // Optional error code/state
```

**Error Codes:**
```
ERROR_UNKNOWN_COMMAND      = 0x01
ERROR_INVALID_PAYLOAD      = 0x02
ERROR_TIMEOUT              = 0x03
ERROR_CAMERA_FAILED        = 0x04
ERROR_OUT_OF_MEMORY        = 0x05
ERROR_CHECKSUM_MISMATCH    = 0x06
ERROR_IMAGE_TOO_LARGE      = 0x07
ERROR_FRAME_INVALID        = 0x08
```

---

## ACK Mechanism (Optional)

For critical commands, sender may request ACK:

```c
// In payload[0], bit 7 can indicate ACK_REQUIRED
#define ACK_REQUIRED_BIT 0x80
```

ACK Response:
```
message_type: MESSAGE_TYPE_ACK
command_id:   command_id being acknowledged
event_id:     matching command event_id
payload:      (empty or status)
```

---

## Image Transfer Protocol

Images are **not** transferred via ESP-NOW. Instead:

1. **ESP32-CAM** captures JPEG and stores locally
2. **ESP32-CAM** sends `CMD_IMAGE_READY` with image size and CRC32
3. **Main ESP32** polls/requests image chunks from ESP32-CAM via HTTP/API (future enhancement) or:
4. **Main ESP32** uploads image file to backend via HTTP POST `/api/camera/upload`

For **this implementation**, the Main ESP32 will:
- Poll the ESP32-CAM's HTTP server to retrieve the image
- Recompress if necessary
- Upload to backend

---

## State Machine: Main ESP32

```
IDLE
  ↓ Backend /api/camera/trigger
COMMAND_QUEUED
  ↓ Send CMD_CAPTURE_IMAGE via ESP-NOW
WAITING_CAPTURE
  ↓ Receive CMD_IMAGE_READY
CAPTURE_SUCCESS / CAPTURE_FAILED
  ↓ Poll /api/camera/image on ESP32-CAM (HTTP)
IMAGE_RETRIEVAL
  ↓ POST /api/camera/upload to CloudGuard backend
UPLOAD_SUCCESS / UPLOAD_FAILED
  ↓
IDLE
```

---

## State Machine: ESP32-CAM

```
IDLE
  ↓ Receive CMD_CAPTURE_IMAGE
CAPTURING
  ↓ JPEG capture complete/failed
CAPTURE_COMPLETE / CAPTURE_FAILED
  ↓ Send CMD_IMAGE_READY
IDLE
```

---

## MAC Address Management

**Hardcoded Configuration (see firmware setup):**

```c
// Main ESP32
uint8_t MAIN_ESP32_MAC[6] = {0x08, 0x3A, 0xF2, 0x12, 0x34, 0x56};

// ESP32-CAM
uint8_t ESP32_CAM_MAC[6] = {0x08, 0x3A, 0xF2, 0xAB, 0xCD, 0xEF};
```

Both devices must add each other as ESP-NOW peers before communication.

---

## Sequence Numbers & Duplicate Detection

Each device maintains:
```c
uint32_t last_sequence_received = 0;
```

- **Sender:** Increments `sequence_number` for each message
- **Receiver:** Ignores messages with `sequence_number <= last_sequence_received`
- **Tolerance:** Allow up to 10-second time window for late arrivals

---

## Checksums & Validation

**Packet-Level:**
```c
uint16_t crc16_xmodem(uint8_t* data, size_t len);
```
Computed on full `CloudGuardMessage` struct.

**Image-Level:**
```c
uint32_t crc32(uint8_t* data, size_t len);
```
Sent with `CMD_IMAGE_READY` to verify download integrity.

---

## Retry & Timeout Strategy

| Command | Timeout | Retries | Total Wait |
|---------|---------|---------|-----------|
| PING | 2000ms | 3 | 6000ms |
| CAPTURE_IMAGE | 5000ms | 2 | 10000ms |
| STATUS_REQUEST | 2000ms | 3 | 6000ms |

- Exponential backoff: wait = base_timeout * (retry_count + 1)
- After total wait, mark command as FAILED

---

## Event ID Assignment

**Backend-Generated:**
- Event IDs from `/api/camera/trigger` are UUIDs/timestamps
- Main ESP32 passes these through to ESP32-CAM

**Main ESP32-Generated:**
- Sequence number for internal commands
- Format: `crc16(device_id + timestamp)` for uniqueness

**Duplicate Prevention:**
- Check `event_id + sequence_number` combination
- Ignore if seen before within 10-second window

---

## Security Considerations

### MAC Validation
```c
bool is_known_peer(uint8_t mac[6]) {
  return memcmp(mac, KNOWN_PEER_MAC, 6) == 0;
}
```

### Payload Validation
- Check `payload_length <= 180`
- Validate all numeric fields are within expected ranges
- Discard messages from unknown MAC addresses

### Timestamp Validation
```c
bool timestamp_is_valid(uint32_t remote_ts_ms) {
  uint32_t local_ts_ms = millis();
  return abs((int32_t)(remote_ts_ms - local_ts_ms)) < 60000; // 60s window
}
```

### CRC Validation (Image)
- Compare received CRC32 against locally computed CRC32
- Retry or report error if mismatch

---

## Debugging & Logging

**Main ESP32 Console Output:**
```
[ESPNOW] TX: PING to AA:BB:CC:DD:EE:FF (seq=1234)
[ESPNOW] RX: PONG from AA:BB:CC:DD:EE:FF (seq=1234, rssi=-45)
[ESPNOW] CMD_CAPTURE_IMAGE sent (event=abc123, timeout=5s)
[ESPNOW] CMD_IMAGE_READY received (size=25600, crc=0xabcd1234)
[ESPNOW] TIMEOUT waiting for response to CMD_CAPTURE_IMAGE
[ESPNOW] ERROR: Unknown command 0xFF
```

**ESP32-CAM Console Output:**
```
[ESPNOW] RX: PING from AA:BB:CC:DD:EE:FF (seq=1234)
[ESPNOW] TX: PONG to AA:BB:CC:DD:EE:FF (seq=1234)
[CAMERA] Capture initiated (quality=90, size=QVGA)
[CAMERA] Capture complete (25600 bytes, crc=0xabcd1234)
[ESPNOW] TX: CMD_IMAGE_READY to AA:BB:CC:DD:EE:FF
```

---

## Testing Checklist

- [ ] Main ESP32 sends PING → ESP32-CAM receives and responds PONG
- [ ] Sequence numbers prevent duplicate processing
- [ ] CAPTURE_IMAGE timeout after 5s if camera unavailable
- [ ] Image CRC32 validation prevents corrupt uploads
- [ ] Unknown peer MAC is rejected
- [ ] Payload length validation prevents buffer overflow
- [ ] Event IDs uniquely track backend triggers → camera → upload
- [ ] Main ESP32 gracefully continues if ESP32-CAM offline
- [ ] Backend continues risk assessment if camera fails
