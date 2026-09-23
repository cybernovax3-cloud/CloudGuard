# CloudGuard Hardware

CloudGuard uses an ESP32 sensor node and an ESP32-CAM for environmental monitoring and event evidence.

```text
ESP32
├── Ultrasonic     -> Flood/water level
├── Rain sensor    -> Rain detection
├── Soil moisture  -> Soil saturation
├── Vibration      -> Ground vibration
├── DHT22          -> Temperature/humidity
├── BMP280         -> Atmospheric pressure
├── MQ-2           -> Smoke/gas
├── MQ-135         -> Air quality
└── OLED           -> Local display
```

## GPIO Mapping

| Component | Connection |
|---|---|
| Ultrasonic TRIG | GPIO 18 |
| Ultrasonic ECHO | GPIO 19 |
| Rain sensor | GPIO 12 |
| Soil moisture | GPIO 35 |
| Vibration DO | GPIO 27 |
| DHT22 data | GPIO 4 |
| MQ-135 analog output | GPIO 34 |
| MQ-2 analog output | GPIO 32 |
| OLED SDA | GPIO 21 |
| OLED SCL | GPIO 22 |

BMP280 uses the dedicated I2C bus defined in the firmware. Exact power, voltage, and board-specific wiring should be checked against the selected modules before field deployment.

MPU6050 is not part of the current CloudGuard hardware and is intentionally not included.
