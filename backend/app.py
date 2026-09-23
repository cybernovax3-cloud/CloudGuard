import csv
import io
import json
import os
from pathlib import Path
from alerts import send_critical_alert, send_forecast_alert
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime, timezone
import math
import re
import uuid
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from forecast_model import forecast_from_history
from edge_decision import assess_edge_risk
from ml_model import predict_risk
from risk_engine import fuse_risk
from sensor_database import (
    get_latest_reading,
    get_latest_readings_by_device,
    get_camera_event,
    get_alerts,
    get_latest_camera_event,
    get_sensor_history,
    initialize_database,
    save_camera_event,
    save_sensor_reading,
    update_camera_event,
)
from vision_model import SUPPORTED_IMAGE_TYPES, analyze_image


app = Flask(__name__)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})


# ============================================
# CLOUDGUARD STATE
# ============================================

latest_data = None
last_seen = None
latest_data_by_device = {}
last_seen_by_device = {}

DEVICE_ID_PATTERN = re.compile(r"^CG[0-9A-Z_-]{1,31}$")
OFFLINE_TIMEOUT = 10
CAMERA_TIMEOUT = 120
CAMERA_COOLDOWN_SECONDS = int(os.getenv("CAMERA_COOLDOWN_SECONDS", "300"))
CAMERA_DIR = Path(__file__).resolve().parent / "camera_uploads"
CAMERA_PATH = CAMERA_DIR / "latest_image"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
camera_state = {
    "available": False,
    "last_capture": None,
    "device_id": None,
    "event_id": None,
    "trigger_reason": None,
    "hazard": None,
    "content_type": None,
    "vision": {"vision_available": False, "vision_status": "UNAVAILABLE"},
}
WEATHER_CACHE_TTL = 300
weather_cache = {"expires_at": 0, "key": None, "data": None}
initialize_database()


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_time_label(value):
    if not value:
        return "N/A"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return str(value)


def _build_report_entry(title, value):
    if value is None:
        return f"{title}: N/A"
    if isinstance(value, (list, tuple)):
        joined = "; ".join(str(item) for item in value if item not in (None, "", []))
        return f"{title}: {joined if joined else 'N/A'}"
    return f"{title}: {value}"


def _report_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def _report_incident_name(reading):
    risks = {
        "Flood Risk": _safe_float(reading.get("current_flood_risk", reading.get("flood_risk"))),
        "Landslide Risk": _safe_float(reading.get("current_landslide_risk", reading.get("landslide_risk"))),
        "Air Quality Risk": _safe_float(reading.get("current_air_gas_risk", reading.get("air_gas_risk"))),
    }
    return max(risks, key=risks.get) if max(risks.values(), default=0) > 0 else "Flood Risk"


def generate_incident_report(device_id=None, incident=None, severity=None, location=None, start=None, end=None):
    selected_device = None if not device_id or device_id == "all" else device_id
    start_at = _report_timestamp(start)
    end_at = _report_timestamp(end)
    latest = latest_data_by_device.get(selected_device) if selected_device else latest_data
    history = get_sensor_history(selected_device, 5000)
    if not history and latest:
        history = [latest]

    def in_window(item):
        timestamp = _report_timestamp(item.get("timestamp"))
        return timestamp is not None and (not start_at or timestamp >= start_at) and (not end_at or timestamp <= end_at)

    readings = [item for item in history if in_window(item)] if (start_at or end_at) else history
    if selected_device is None and not readings:
        readings = [item for item in get_sensor_history(None, 5000) if in_window(item)] if (start_at or end_at) else get_sensor_history(None, 5000)
    readings = sorted(readings, key=lambda item: item.get("timestamp", ""))
    current = readings[-1] if readings else latest
    if not current:
        current = {"device_id": selected_device or "N/A", "overall_status": "N/A"}

    active_incident = incident or _report_incident_name(current)
    if active_incident != "All Incidents":
        readings = [item for item in readings if _report_incident_name(item) == active_incident]
    if severity and severity != "all":
        readings = [item for item in readings if str(item.get("overall_status", "")).upper() == str(severity).upper()]

    device_ids = sorted({item.get("device_id") for item in readings if item.get("device_id")})
    timestamps = [item.get("timestamp") for item in readings if item.get("timestamp")]
    first_timestamp = timestamps[0] if timestamps else current.get("timestamp")
    last_timestamp = timestamps[-1] if timestamps else current.get("timestamp")
    first_at = _report_timestamp(first_timestamp)
    last_at = _report_timestamp(last_timestamp)
    duration_minutes = round((last_at - first_at).total_seconds() / 60) if first_at and last_at else None
    duration = f"{_format_time_label(first_timestamp)}–{_format_time_label(last_timestamp)}" if first_timestamp and last_timestamp else "N/A"
    if duration_minutes is not None:
        duration = f"{duration} ({duration_minutes} min)"

    def peak(key):
        values = [_safe_float(item.get(key), None) for item in readings]
        values = [value for value in values if value is not None]
        return round(max(values), 1) if values else 0

    peak_rainfall = peak("rainfall")
    peak_water_level = peak("water_level")
    peak_soil_moisture = peak("soil_moisture")
    peak_temperature = peak("temperature")
    peak_humidity = peak("humidity")
    maximum_risk = peak("overall_risk")
    status = severity if severity and severity != "all" else (current.get("overall_status") or "N/A")

    sensor_evidence_rows = []
    evidence_fields = [("Rainfall", "rainfall", "mm/hr"), ("Water Level", "water_level", "cm"), ("Soil Moisture", "soil_moisture", "%"), ("Temperature", "temperature", "°C"), ("Humidity", "humidity", "%")]
    for item in readings:
        for label, key, unit in evidence_fields:
            value = item.get(key)
            if value is not None:
                sensor_evidence_rows.append({"timestamp": _format_time_label(item.get("timestamp")), "device_id": item.get("device_id", "N/A"), "sensor": label, "value": f"{_safe_float(value):.1f} {unit}", "status": item.get("overall_status", "N/A")})
    sensor_evidence_rows = sensor_evidence_rows[-40:]
    sensor_evidence = [f"{row['timestamp']} {row['sensor']}: {row['value']} ({row['status']})" for row in sensor_evidence_rows]

    risk_trend = [{"timestamp": _format_time_label(item.get("timestamp")), "value": round(_safe_float(item.get("overall_risk")), 1), "status": item.get("overall_status", "N/A")} for item in readings[-60:]]
    camera_event = get_latest_camera_event(selected_device)
    camera_evidence = []
    if camera_event:
        vision = camera_event.get("vision") or {}
        camera_evidence.append({"timestamp": _format_time_label(camera_event.get("timestamp")), "device_id": camera_event.get("device_id"), "image_url": "/api/camera/latest?raw=1" if camera_event.get("image_path") else None, "trigger": camera_event.get("trigger_reason"), "hazard": camera_event.get("hazard"), "status": vision.get("vision_status", camera_event.get("status")), "message": vision.get("message", "No visual assessment available")})
    camera_evidence_text = [f"{item['timestamp']} {item['status']}: {item['message']}" for item in camera_evidence] or ["No camera evidence available for this incident."]

    alerts = [item for item in get_alerts(limit=1000, device_id=selected_device) if (not start_at or (_report_timestamp(item.get("timestamp")) and _report_timestamp(item.get("timestamp")) >= start_at)) and (not end_at or (_report_timestamp(item.get("timestamp")) and _report_timestamp(item.get("timestamp")) <= end_at))]
    if severity and severity != "all":
        alerts = [item for item in alerts if str(item.get("severity", "")).upper() == str(severity).upper()]
    alert_history_rows = [{"timestamp": _format_time_label(item.get("timestamp")), "hazard": item.get("hazard", "Environmental"), "message": item.get("message", "Alert received"), "severity": item.get("severity", "INFO")} for item in reversed(alerts[-25:])]
    alert_history = [f"{item['timestamp']} {item['hazard']}: {item['message']} ({item['severity']})" for item in alert_history_rows] or ["No alert history captured for the selected filters."]
    response_timeline = [{"stage": "Detected", "timestamp": _format_time_label(first_timestamp), "detail": f"Sensor evidence received from {', '.join(device_ids) or 'the active node'}."}, {"stage": "Risk Assessment", "timestamp": _format_time_label(last_timestamp), "detail": f"Maximum risk reached {maximum_risk:.1f}/100."}]
    if alert_history_rows:
        response_timeline.append({"stage": "Alert", "timestamp": alert_history_rows[0]["timestamp"], "detail": alert_history_rows[0]["message"]})
    response_timeline.append({"stage": "Monitoring", "timestamp": _format_time_label(last_timestamp), "detail": f"Monitoring continued through {len(readings)} stored reading(s)."})
    response_timeline_text = [f"{item['timestamp']} {item['stage']}: {item['detail']}" for item in response_timeline]
    summary = f"{active_incident} was recorded in {location or 'Zone A'} from {duration}. The highest recorded risk was {maximum_risk:.1f}/100 with peak rainfall of {peak_rainfall:.1f} mm/hr and peak water level of {peak_water_level:.1f} cm. Evidence is based on {len(readings)} sensor reading(s), {len(alert_history_rows)} alert(s), and {len(camera_evidence)} camera event(s)."

    return {"incident": active_incident, "location": location or "Zone A", "duration": duration, "device_id": selected_device or (device_ids[0] if len(device_ids) == 1 else "All Nodes"), "severity": status, "no_data": not readings, "peak_rainfall": peak_rainfall, "peak_water_level": peak_water_level, "maximum_risk": maximum_risk, "sensor_evidence": sensor_evidence, "camera_evidence": camera_evidence_text, "alert_history": alert_history, "response_timeline": response_timeline_text, "overview": {"incident": active_incident, "severity": status, "risk": maximum_risk, "device": selected_device or (device_ids[0] if len(device_ids) == 1 else "All Nodes"), "duration": duration}, "peak_conditions": {"rainfall": peak_rainfall, "water_level": peak_water_level, "soil_moisture": peak_soil_moisture, "temperature": peak_temperature, "humidity": peak_humidity}, "risk_trend": risk_trend, "sensor_evidence_rows": sensor_evidence_rows, "camera_evidence_items": camera_evidence, "alert_history_rows": alert_history_rows, "response_timeline_items": response_timeline, "summary": "No incident data available for the selected scope." if not readings else summary, "filters": {"devices": sorted({item.get("device_id") for item in get_latest_readings_by_device() if item.get("device_id")}), "incidents": ["Flood Risk", "Landslide Risk", "Air Quality Risk", "All Incidents"], "severities": ["All", "NORMAL", "WATCH", "WARNING", "CRITICAL"], "locations": ["All Zones", "Zone A"]}}


def export_incident_report(report, export_format="json"):
    fmt = (export_format or "json").lower()
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["field", "value"])
        writer.writerow([f"Incident: {report.get('incident', 'Unknown')}", ""])
        for key in ["incident", "location", "duration", "peak_rainfall", "peak_water_level", "maximum_risk"]:
            if key == "incident":
                continue
            writer.writerow([key, report.get(key, "")])
        writer.writerow(["sensor_evidence", "; ".join(report.get("sensor_evidence", []))])
        writer.writerow(["camera_evidence", "; ".join(report.get("camera_evidence", []))])
        writer.writerow(["alert_history", "; ".join(report.get("alert_history", []))])
        writer.writerow(["response_timeline", "; ".join(report.get("response_timeline", []))])
        return output.getvalue().encode("utf-8")

    if fmt == "pdf":
        lines = [
            "CloudGuard Incident Report",
            "",
            f"Incident: {report.get('incident', 'Unknown')}",
            f"Location: {report.get('location', 'Zone A')}",
            f"Duration: {report.get('duration', 'N/A')}",
            "",
            f"Peak rainfall: {report.get('peak_rainfall', 'N/A')}",
            f"Peak water level: {report.get('peak_water_level', 'N/A')}",
            f"Maximum risk: {report.get('maximum_risk', 'N/A')}",
            "",
            "Sensor evidence",
            *[f"- {line}" for line in report.get("sensor_evidence", [])],
            "",
            "Camera evidence",
            *[f"- {line}" for line in report.get("camera_evidence", [])],
            "",
            "Alert history",
            *[f"- {line}" for line in report.get("alert_history", [])],
            "",
            "Response timeline",
            *[f"- {line}" for line in report.get("response_timeline", [])],
        ]
        text = "\n".join(lines)
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines = []
        y = 780
        for line in escaped.split("\n"):
            content_lines.append(f"BT /F1 12 Tf 72 {y} Td ({line}) Tj ET")
            y -= 18
        content_stream = "\n".join(content_lines).encode("latin-1", errors="replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content_stream), content_stream),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for idx, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{idx} 0 obj\n".encode("latin-1"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")
        xref_start = len(pdf)
        pdf.extend(f"xref\n0 {len(objects)+1}\n".encode("latin-1"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
        pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("latin-1"))
        return bytes(pdf)

    report_json = json.dumps(report, indent=2, ensure_ascii=False)
    return report_json.encode("utf-8")


def _timestamp_epoch(timestamp):
    try:
        return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


for _reading in get_latest_readings_by_device():
    _device_id = _reading.get("device_id")
    _timestamp = _timestamp_epoch(_reading.get("timestamp"))
    if _device_id and _timestamp is not None:
        latest_data_by_device[_device_id] = _reading
        last_seen_by_device[_device_id] = _timestamp
latest_data = get_latest_reading()
last_seen = last_seen_by_device.get(latest_data.get("device_id")) if latest_data else None


# ============================================
# HOME
# ============================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "CloudGuard Backend",
        "version": "4.0"
    })


# ============================================
# HEALTH CHECK
# ============================================

@app.route("/api/health")
def health():
    return jsonify({
        "backend": "online",
        "api": "online",
        "alert_channel": "available" if os.getenv("ALERT_PHONE") or (os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and os.getenv("TWILIO_FROM_NUMBER") and os.getenv("ALERT_RECIPIENTS")) else "unavailable"
    })


# ============================================
# VALIDATION
# ============================================

REQUIRED_FIELDS = [
    "device_id",
    "rainfall",
    "rain_sensor_percent",
    "temperature",
    "humidity",
    "pressure",
    "water_level",
    "water_rise",
    "soil_moisture",
    "tilt_change",
    "vibration",
    "mq2_raw",
    "mq2_change",
    "mq135_raw",
    "mq135_change",

    # Local risk values
    "flood_risk",
    "landslide_risk",
    "air_gas_risk",
    "overall_risk",

    # Local status values
    "flood_status",
    "landslide_status",
    "mq2_status",
    "mq135_status",
    "overall_status"
]


NUMERIC_FIELDS = [
    "rainfall",
    "rain_sensor_percent",
    "temperature",
    "humidity",
    "pressure",
    "water_level",
    "water_rise",
    "soil_moisture",
    "tilt_change",
    "mq2_raw",
    "mq2_change",
    "mq135_raw",
    "mq135_change",
    "flood_risk",
    "landslide_risk",
    "air_gas_risk",
    "overall_risk"
]


STATUS_FIELDS = [
    "flood_status",
    "landslide_status",
    "mq2_status",
    "mq135_status",
    "overall_status"
]


def validate_sensor_data(data):

    # JSON must be an object
    if not isinstance(data, dict):
        return False, "JSON body must be an object"

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            return False, f"Missing field: {field}"

    # Device IDs are stable node identifiers such as CG01, CG02, or CG-A1.
    if not isinstance(data["device_id"], str):
        return False, "device_id must be a string"

    if not DEVICE_ID_PATTERN.fullmatch(data["device_id"]):
        return False, "device_id must match the CloudGuard format CG followed by 2-32 uppercase characters, digits, _ or -"

    # Numeric validation
    for field in NUMERIC_FIELDS:

        value = data[field]

        if isinstance(value, bool):
            return False, f"{field} must be numeric"

        if not isinstance(value, (int, float)):
            return False, f"{field} must be numeric"

        if not math.isfinite(float(value)):
            return False, f"{field} cannot be NaN or Infinity"

    numeric_limits = {
        "rainfall": (0, 500),
        "temperature": (-40, 85),
        "pressure": (800, 1200),
        "water_level": (0, 500),
        "water_rise": (-500, 500),
        "tilt_change": (-180, 180),
    }
    for field, (minimum, maximum) in numeric_limits.items():
        value = float(data[field])
        if value < minimum or value > maximum:
            return False, f"{field} must be between {minimum} and {maximum}"

    for field, minimum, maximum in (("latitude", -90, 90), ("longitude", -180, 180)):
        if field in data:
            if isinstance(data[field], bool) or not isinstance(data[field], (int, float)) or not math.isfinite(float(data[field])):
                return False, f"{field} must be numeric"
            if not minimum <= float(data[field]) <= maximum:
                return False, f"{field} must be between {minimum} and {maximum}"

    # Percentage validation
    percentage_fields = [
        "rain_sensor_percent",
        "humidity",
        "soil_moisture"
    ]

    for field in percentage_fields:

        value = float(data[field])

        if value < 0 or value > 100:
            return False, f"{field} must be between 0 and 100"

    # Risk validation
    risk_fields = [
        "flood_risk",
        "landslide_risk",
        "air_gas_risk",
        "overall_risk"
    ]

    for field in risk_fields:

        value = float(data[field])

        if value < 0 or value > 100:
            return False, f"{field} must be between 0 and 100"

    # Vibration MUST be a real JSON boolean
    if not isinstance(data["vibration"], bool):
        return False, "vibration must be true or false"

    # Status validation
    allowed_statuses = [
        "NORMAL",
        "WATCH",
        "WARNING",
        "CRITICAL"
    ]

    for field in STATUS_FIELDS:

        if not isinstance(data[field], str):
            return False, f"{field} must be a string"

        if data[field] not in allowed_statuses:
            return False, f"Invalid status for {field}"

    return True, "Valid"


# ============================================
# RECEIVE ESP32 / ESP32-CAM DATA
# ============================================

@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():

    global latest_data
    global last_seen
    global latest_data_by_device
    global last_seen_by_device

    data = request.get_json(silent=True)

    # ----------------------------------------
    # VALIDATE
    # ----------------------------------------

    valid, message = validate_sensor_data(data)

    if not valid:

        return jsonify({
            "success": False,
            "message": message
        }), 400

    try:

        # ------------------------------------
        # COPY DATA
        # ------------------------------------

        latest_data = {

            "device_id": data["device_id"],

            "rainfall": float(data["rainfall"]),
            "rain_sensor_percent": float(
                data["rain_sensor_percent"]
            ),

            "temperature": float(data["temperature"]),
            "humidity": float(data["humidity"]),
            "pressure": float(data["pressure"]),

            "water_level": float(data["water_level"]),
            "water_rise": float(data["water_rise"]),

            "soil_moisture": float(data["soil_moisture"]),
            "tilt_change": float(data["tilt_change"]),
            "vibration": data["vibration"],

            "mq2_raw": float(data["mq2_raw"]),
            "mq2_change": float(data["mq2_change"]),

            "mq135_raw": float(data["mq135_raw"]),
            "mq135_change": float(data["mq135_change"]),

            # --------------------------------
            # LOCAL ESP32 RISK
            # --------------------------------

            "flood_risk": float(data["flood_risk"]),

            "landslide_risk": float(
                data["landslide_risk"]
            ),

            "air_gas_risk": float(
                data["air_gas_risk"]
            ),

            "overall_risk": float(
                data["overall_risk"]
            ),

            # --------------------------------
            # LOCAL ESP32 STATUS
            # --------------------------------

            "flood_status": data["flood_status"],
            "landslide_status": data["landslide_status"],
            "mq2_status": data["mq2_status"],
            "mq135_status": data["mq135_status"],
            "overall_status": data["overall_status"],

            # --------------------------------
            # FLASK RECEIVED TIMESTAMP
            # --------------------------------

            "timestamp": datetime.now(
                timezone.utc
            ).isoformat()
        }
        for coordinate in ("latitude", "longitude"):
            if coordinate in data:
                latest_data[coordinate] = float(data[coordinate])

        previous_reading = latest_data_by_device.get(latest_data["device_id"])
        latest_data["edge_decision"] = assess_edge_risk(latest_data, previous_reading)
        latest_data_by_device[latest_data["device_id"]] = latest_data

        current_model = predict_risk(
            latest_data["rainfall"],
            latest_data["humidity"],
            latest_data["pressure"],
            latest_data["water_level"]
        )
        latest_data["current_model_status"] = current_model["status"]
        latest_data["current_model_confidence"] = current_model["confidence"]
        latest_data["current_model_available"] = current_model.get("available", False)
        latest_data["current_model_message"] = current_model.get("message")
        latest_data["current_model_risk"] = {
            "NORMAL": 0,
            "WATCH": 33.33,
            "WARNING": 66.67,
            "CRITICAL": 100
        }.get(current_model["status"])

        save_sensor_reading(latest_data)
        send_forecast_alert(
            latest_data,
            forecast_from_history(get_sensor_history(latest_data["device_id"], 5000))
        )

        # ------------------------------------
        # UPDATE LAST SEEN
        # ------------------------------------

        last_seen = time.time()
        last_seen_by_device[latest_data["device_id"]] = last_seen


        # ====================================
        # TWILIO CRITICAL ALERT
        # ====================================
        #
        # SMS will ONLY be attempted when:
        #
        # overall_status == "CRITICAL"
        #
        # NORMAL  -> no SMS
        # WATCH   -> no SMS
        # WARNING -> no SMS
        # CRITICAL -> SMS
        #
        # ====================================

        send_critical_alert(latest_data)


        # ------------------------------------
        # PRINT
        # ------------------------------------

        print("\n====================================")
        print("CLOUDGUARD SENSOR UPDATE")
        print("====================================")

        print(
            "Device:",
            latest_data["device_id"]
        )

        print(
            "Temperature:",
            latest_data["temperature"]
        )

        print(
            "Humidity:",
            latest_data["humidity"]
        )

        print(
            "Pressure:",
            latest_data["pressure"]
        )

        print(
            "Rain:",
            latest_data["rain_sensor_percent"]
        )

        print(
            "Water:",
            latest_data["water_level"]
        )

        print(
            "Water rise:",
            latest_data["water_rise"]
        )

        print(
            "Soil:",
            latest_data["soil_moisture"]
        )

        print(
            "Tilt:",
            latest_data["tilt_change"]
        )

        print(
            "Vibration:",
            latest_data["vibration"]
        )

        print(
            "MQ2:",
            latest_data["mq2_raw"]
        )

        print(
            "MQ135:",
            latest_data["mq135_raw"]
        )

        print("------------------------------------")

        print(
            "Flood risk:",
            latest_data["flood_risk"]
        )

        print(
            "Landslide risk:",
            latest_data["landslide_risk"]
        )

        print(
            "Air/Gas risk:",
            latest_data["air_gas_risk"]
        )

        print(
            "Overall risk:",
            latest_data["overall_risk"]
        )

        print(
            "Overall status:",
            latest_data["overall_status"]
        )

        print("====================================\n")


        # ------------------------------------
        # RESPONSE
        # ------------------------------------

        return jsonify({

            "success": True,

            "device_id": latest_data["device_id"],

            "current_risk": latest_data["overall_risk"],

            "status": latest_data["overall_status"],

            "timestamp": latest_data["timestamp"],

            "message":
                "Sensor data received successfully",

            "data": latest_data

        }), 200


    except Exception as e:

        print("SERVER ERROR:", e)

        return jsonify({

            "success": False,

            "message":
                f"Server error: {str(e)}"

        }), 500


# ============================================
# GET LATEST DATA
# ============================================

@app.route("/api/latest-data", methods=["GET"])
def get_latest_data():
    device_id = request.args.get("device_id")
    reading = get_latest_reading(device_id) if device_id else latest_data
    if reading is None:
        return jsonify({"online": False, "message": "Waiting for ESP32 sensor data"}), 200

    reading_device_id = reading.get("device_id")
    seen_at = last_seen_by_device.get(reading_device_id)
    if seen_at is None:
        seen_at = _timestamp_epoch(reading.get("timestamp"))
    online = seen_at is not None and time.time() - seen_at <= OFFLINE_TIMEOUT
    if not online:
        return jsonify({
            "online": False,
            "device_id": reading_device_id,
            "last_seen": reading.get("timestamp"),
            "message": "Sensor node is stale or offline",
        }), 200

    return jsonify({
        "online": True,
        "device_id": reading_device_id,
        "last_seen": reading.get("timestamp"),
        "data": reading,
    }), 200


# ============================================
# HISTORY AND FORECAST
# ============================================

@app.route("/api/sensor-history", methods=["GET"])
def sensor_history():
    try:
        limit = int(request.args.get("limit", 256))
    except ValueError:
        return jsonify({"success": False, "message": "limit must be an integer"}), 400
    return jsonify({"success": True, "readings": get_sensor_history(request.args.get("device_id"), limit)})


@app.route("/api/history", methods=["GET"])
def history():
    return sensor_history()


@app.route("/api/devices", methods=["GET"])
def devices():
    now = time.time()
    device_summaries = []
    for reading in get_latest_readings_by_device():
        device_id = reading.get("device_id")
        seen_at = last_seen_by_device.get(device_id) or _timestamp_epoch(reading.get("timestamp"))
        device_summaries.append({
            "device_id": device_id,
            "online": seen_at is not None and now - seen_at <= OFFLINE_TIMEOUT,
            "last_seen": reading.get("timestamp"),
            "overall_status": reading.get("overall_status"),
            "overall_risk": reading.get("overall_risk"),
            "flood_risk": reading.get("current_flood_risk", reading.get("flood_risk")),
            "landslide_risk": reading.get("current_landslide_risk", reading.get("landslide_risk")),
            "air_gas_risk": reading.get("current_air_gas_risk", reading.get("air_gas_risk")),
            "fire_risk": reading.get("fire_risk"),
            "rainfall": reading.get("rainfall"),
            "water_level": reading.get("water_level"),
            "water_rise": reading.get("water_rise"),
            "soil_moisture": reading.get("soil_moisture"),
            "temperature": reading.get("temperature"),
            "humidity": reading.get("humidity"),
            "mq135_raw": reading.get("mq135_raw"),
            "latitude": reading.get("latitude"),
            "longitude": reading.get("longitude"),
        })
    return jsonify({"success": True, "devices": device_summaries})


@app.route("/api/devices/<device_id>", methods=["GET"])
def device(device_id):
    if not DEVICE_ID_PATTERN.fullmatch(device_id):
        return jsonify({"success": False, "message": "Invalid device_id"}), 400
    reading = get_latest_reading(device_id)
    if reading is None:
        return jsonify({"success": False, "message": "Device has no readings"}), 404
    seen_at = last_seen_by_device.get(device_id) or _timestamp_epoch(reading.get("timestamp"))
    return jsonify({
        "success": True,
        "device_id": device_id,
        "online": seen_at is not None and time.time() - seen_at <= OFFLINE_TIMEOUT,
        "last_seen": reading.get("timestamp"),
        "data": reading,
    })


@app.route("/api/forecast", methods=["GET"])
def forecast():
    return jsonify(forecast_from_history(get_sensor_history(request.args.get("device_id"), 5000)))


@app.route("/api/forecast/history", methods=["GET"])
def forecast_history():
    readings = get_sensor_history(request.args.get("device_id"), 5000)
    return jsonify({
        "forecast_available": len(readings) >= 24,
        "horizon_hours": 6,
        "history": [
            {"timestamp": item.get("timestamp"), "current_risk": item.get("overall_risk")}
            for item in readings
        ]
    })


# ============================================
# RISK PREDICTION & WEATHER INTELLIGENCE API
# ============================================

@app.route("/api/prediction", methods=["GET"])
def get_prediction():
    device_id = request.args.get("device_id")
    readings = get_sensor_history(device_id, 100)
    latest = get_latest_reading(device_id) if device_id else latest_data
    if not latest or not readings or len(readings) < 3:
        return jsonify({
            "available": False,
            "message": "Awaiting prediction data"
        }), 200

    times = [_timestamp_epoch(r.get("timestamp")) for r in readings if _timestamp_epoch(r.get("timestamp")) is not None]
    water_vals = [_safe_float(r.get("water_level")) for r in readings]
    rain_vals = [_safe_float(r.get("rainfall")) for r in readings]
    risk_vals = [_safe_float(r.get("overall_risk")) for r in readings]

    w_trend = (water_vals[-1] - water_vals[0]) / max(1, len(water_vals)) if len(water_vals) >= 2 else 0.0
    r_trend = (rain_vals[-1] - rain_vals[0]) / max(1, len(rain_vals)) if len(rain_vals) >= 2 else 0.0
    rk_trend = (risk_vals[-1] - risk_vals[0]) / max(1, len(risk_vals)) if len(risk_vals) >= 2 else 0.0

    cur_risk = _safe_float(latest.get("overall_risk"))
    cur_rain = _safe_float(latest.get("rainfall"))
    cur_water = _safe_float(latest.get("water_level"))

    def calc_horizon(factor, hours):
        pred_risk = min(100.0, max(0.0, round(cur_risk + rk_trend * hours * 8 + w_trend * hours * 5, 1)))
        pred_rain = round(max(0.0, cur_rain + r_trend * hours * 2), 1)
        pred_water = round(max(0.0, (cur_water + w_trend * hours * 10) / 100.0), 2)
        
        status = "NORMAL"
        if pred_risk >= 80: status = "CRITICAL"
        elif pred_risk >= 60: status = "WARNING"
        elif pred_risk >= 30: status = "WATCH"
        
        trend_str = "Increasing" if rk_trend > 0.1 else ("Decreasing" if rk_trend < -0.1 else "Stable")
        trend_arrow = "↑" if rk_trend > 0.1 else ("↓" if rk_trend < -0.1 else "→")
        
        return {
            "score": pred_risk,
            "level": status,
            "predicted_rainfall_mm": pred_rain,
            "predicted_water_level_m": pred_water,
            "trend": trend_str,
            "trend_arrow": trend_arrow
        }

    return jsonify({
        "available": True,
        "horizon_1h": calc_horizon(1.0, 1),
        "horizon_3h": calc_horizon(1.5, 3),
        "horizon_6h": calc_horizon(2.0, 6),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


def _weather_condition(code, rain):
    if rain is not None and rain > 15:
        return "Heavy Rain", "🌧"
    if rain is not None and rain > 2:
        return "Light Rain", "🌦"
    if code in {0, 1}:
        return "Clear", "☀"
    if code in {2, 3}:
        return "Cloudy", "☁"
    if code in {45, 48}:
        return "Fog", "🌫"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "Rain", "🌧"
    if code in {71, 73, 75, 77, 85, 86}:
        return "Snow", "❄"
    if code in {95, 96, 99}:
        return "Thunderstorm", "⛈"
    return "Conditions monitored", "☁"


def _get_external_weather():
    global weather_cache
    try:
        latitude = float(os.getenv("WEATHER_LATITUDE", "13.0827"))
        longitude = float(os.getenv("WEATHER_LONGITUDE", "80.2707"))
    except ValueError:
        latitude, longitude = 13.0827, 80.2707
    cache_key = f"{latitude:.4f},{longitude:.4f}"
    now = time.time()
    if weather_cache["key"] == cache_key and weather_cache["expires_at"] > now and weather_cache["data"]:
        return weather_cache["data"]

    params = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,pressure_msl",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "forecast_days": 1,
        "timezone": "auto",
    })
    try:
        request = Request(
            f"https://api.open-meteo.com/v1/forecast?{params}",
            headers={"User-Agent": "CloudGuard/1.0"},
        )
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        current = payload.get("current", {})
        hourly = payload.get("hourly", {})
        rain = _safe_float(current.get("precipitation"), None)
        code = int(current.get("weather_code", -1))
        condition, icon = _weather_condition(code, rain)
        times = hourly.get("time", [])[:8]
        temperatures = hourly.get("temperature_2m", [])[:8]
        probabilities = hourly.get("precipitation_probability", [])[:8]
        codes = hourly.get("weather_code", [])[:8]
        hourly_items = []
        for index, timestamp in enumerate(times):
            hour_code = int(codes[index]) if index < len(codes) and codes[index] is not None else -1
            _, hour_icon = _weather_condition(hour_code, None)
            hourly_items.append({
                "time": str(timestamp).replace("T", " ")[11:16],
                "icon": hour_icon,
                "temp": f"{temperatures[index]:.1f}°C" if index < len(temperatures) else "N/A",
                "rain_prob": f"{probabilities[index]}%" if index < len(probabilities) else "N/A",
            })
        result = {
            "available": True,
            "source": "Open-Meteo",
            "location": {"latitude": latitude, "longitude": longitude},
            "current": {
                "condition": condition,
                "icon": icon,
                "temperature": f"{current.get('temperature_2m', 'N/A')}°C",
                "rain": f"{rain} mm" if rain is not None else "N/A",
                "rain_probability": f"{probabilities[0]}%" if probabilities else "N/A",
                "wind": f"{current.get('wind_speed_10m', 'N/A')} km/h",
                "humidity": f"{current.get('relative_humidity_2m', 'N/A')}%",
                "pressure": f"{current.get('pressure_msl', 'N/A')} hPa",
            },
            "hourly": hourly_items,
            "hourly_message": "Forecast provided by Open-Meteo",
            "warning": {"active": code in {95, 96, 99}, "message": "Thunderstorm conditions detected. Verify local alerts." if code in {95, 96, 99} else None},
            "ai_insight": {"title": "External weather context", "summary": "Weather provider data is available while field sensors are offline.", "confidence": None, "factors": [], "updated_at": datetime.now(timezone.utc).isoformat()},
        }
        weather_cache = {"expires_at": now + WEATHER_CACHE_TTL, "key": cache_key, "data": result}
        return result
    except Exception as error:
        return {"available": False, "message": "Weather provider unavailable", "error": str(error)}


@app.route("/api/weather", methods=["GET"])
def get_weather():
    device_id = request.args.get("device_id")
    latest = get_latest_reading(device_id) if device_id else latest_data
    readings = get_sensor_history(device_id, 50)
    if not latest:
        return jsonify(_get_external_weather()), 200

    temp = _safe_float(latest.get("temperature"), None)
    humidity = _safe_float(latest.get("humidity"), None)
    rain = _safe_float(latest.get("rainfall"), None)
    pressure = _safe_float(latest.get("pressure"), None)
    soil = _safe_float(latest.get("soil_moisture"), None)
    water = _safe_float(latest.get("water_level"), None)
    wind = _safe_float(latest.get("wind_speed", latest.get("wind")), None)

    if all(value is None for value in (temp, humidity, rain, pressure, soil, water, wind)):
        return jsonify(_get_external_weather()), 200

    if rain is not None and rain > 15:
        condition = "Heavy Rain"
        icon = "🌧"
    elif rain is not None and rain > 2:
        condition = "Light Rain"
        icon = "🌦"
    elif humidity is not None and humidity > 80:
        condition = "Cloudy / Humid"
        icon = "☁"
    else:
        condition = "Partly Cloudy"
        icon = "⛅"

    rain_probability = latest.get("rain_probability")
    has_warning = (rain is not None and rain > 10) or (water is not None and water > 100) or (pressure is not None and pressure < 995)
    warning_message = "Heavy rainfall and elevated water levels detected in monitored zone. Monitor drainage channels closely." if has_warning else None

    factors = []
    if rain is not None and rain > 2: factors.append({"name": "Rainfall", "direction": "Observed"})
    if water is not None and water > 20: factors.append({"name": "Water Level", "direction": "Elevated"})
    if soil is not None and soil > 60: factors.append({"name": "Soil Moisture", "direction": "Elevated"})
    if temp is not None and temp > 32: factors.append({"name": "Temperature", "direction": "Elevated"})
    
    insight_text = "Environmental sensor synthesis is available from the current telemetry."
    if has_warning:
        insight_text = f"Heavy rainfall ({rain} mm/hr) and elevated water level ({water} cm) indicate increasing flood risk."
    elif rain is not None and rain > 0:
        insight_text = f"Active precipitation ({rain} mm/hr) detected in the monitored area."

    return jsonify({
        "available": True,
        "current": {
            "condition": condition,
            "icon": icon,
            "temperature": f"{temp}°C" if temp is not None else "N/A",
            "rain": f"{rain} mm/hr" if rain is not None else "N/A",
            "rain_probability": f"{rain_probability}%" if rain_probability is not None else "N/A",
            "wind": f"{wind} km/h" if wind is not None else "N/A",
            "humidity": f"{humidity}%" if humidity is not None else "N/A",
            "pressure": f"{pressure} hPa" if pressure is not None else "N/A"
        },
        "hourly": [],
        "hourly_message": "Hourly forecast unavailable",
        "warning": {
            "active": has_warning,
            "message": warning_message
        },
        "ai_insight": {
            "title": "Increasing Flood Risk" if has_warning else "Stable Environmental Conditions",
            "summary": insight_text,
            "confidence": None,
            "factors": factors,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    }), 200


# ============================================
# CAMERA AND VISION
# ============================================

@app.route("/api/camera/trigger", methods=["POST"])
def camera_trigger():
    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id") or (latest_data or {}).get("device_id")
    if not isinstance(device_id, str) or not DEVICE_ID_PATTERN.fullmatch(device_id):
        return jsonify({"success": False, "message": "A valid device_id is required"}), 400
    hazard = str(payload.get("hazard", "ENVIRONMENT")).upper()
    reason = str(payload.get("trigger_reason", "Confirmed critical event"))[:256]
    now = datetime.now(timezone.utc)
    recent = get_latest_camera_event(device_id)
    if recent:
        recent_time = _timestamp_epoch(recent.get("timestamp"))
        if recent_time is not None and now.timestamp() - recent_time < CAMERA_COOLDOWN_SECONDS and recent.get("hazard") == hazard:
            return jsonify({"success": False, "duplicate": True, "message": "Camera trigger suppressed during cooldown", "event": recent}), 409
    event = {
        "event_id": f"{device_id}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "device_id": device_id,
        "timestamp": now.isoformat(),
        "trigger_reason": reason,
        "hazard": hazard,
        "status": "TRIGGERED",
        "image_path": None,
        "content_type": None,
        "vision": None,
        "updated_at": now.isoformat(),
    }
    save_camera_event(event)
    camera_state.update({"event_id": event["event_id"], "device_id": device_id, "trigger_reason": reason, "hazard": hazard})
    return jsonify({"success": True, "camera_triggered": True, "hardware_status": "PENDING", "event": event}), 202


@app.route("/api/camera/upload", methods=["POST"])
def camera_upload():
    image = request.files.get("image") or request.files.get("file")
    if image is None or not image.filename:
        return jsonify({"success": False, "message": "image file is required"}), 400
    if image.mimetype not in SUPPORTED_IMAGE_TYPES:
        return jsonify({"success": False, "message": "Only JPEG, PNG, and WebP images are accepted"}), 415
    content = image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        return jsonify({"success": False, "message": "Image exceeds the 5 MB limit"}), 413
    signatures = (("image/jpeg", b"\xff\xd8\xff"), ("image/png", b"\x89PNG\r\n\x1a\n"), ("image/webp", b"RIFF"))
    if not any(image.mimetype == mime and content.startswith(signature) for mime, signature in signatures):
        return jsonify({"success": False, "message": "Image content does not match its declared type"}), 400
    device_id = request.form.get("device_id") or (latest_data or {}).get("device_id") or "unknown"
    event_id = request.form.get("event_id")
    event = get_camera_event(event_id) if event_id else None
    if event_id and event is None:
        return jsonify({"success": False, "message": "Unknown camera event_id"}), 404
    if event and event["device_id"] != device_id:
        return jsonify({"success": False, "message": "Camera event device mismatch"}), 400
    if event is None:
        now = datetime.now(timezone.utc)
        event = {
            "event_id": f"{device_id}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            "device_id": device_id,
            "timestamp": now.isoformat(),
            "trigger_reason": "Upload without recorded trigger",
            "hazard": "UNKNOWN",
            "status": "UNTRIGGERED_UPLOAD",
            "vision": None,
            "updated_at": now.isoformat(),
        }
        save_camera_event(event)
    CAMERA_DIR.mkdir(exist_ok=True)
    temp_path = CAMERA_DIR / "upload.tmp"
    temp_path.write_bytes(content)
    temp_path.replace(CAMERA_PATH)
    captured_at = datetime.now(timezone.utc).isoformat()
    vision = analyze_image(str(CAMERA_PATH), image.mimetype)
    update_camera_event(event["event_id"], status="CAPTURED", image_path=str(CAMERA_PATH), content_type=image.mimetype, vision=vision)
    camera_state.update({"available": True, "last_capture": captured_at, "device_id": device_id, "event_id": event["event_id"], "trigger_reason": event["trigger_reason"], "hazard": event["hazard"], "content_type": image.mimetype, "vision": vision})
    if vision.get("vision_status") == "FIRE":
        send_critical_alert({
            **(latest_data or {}),
            "device_id": request.form.get("device_id") or (latest_data or {}).get("device_id", "unknown"),
            "overall_status": "CRITICAL",
            "hazard": "FIRE",
            "alert_message": "CloudGuard Critical Alert: Camera evidence indicates possible fire. Immediate response recommended."
        })
    return jsonify({"success": True, "camera": camera_state, "image_url": "/api/camera/latest?raw=1"}), 201


@app.route("/api/camera/latest", methods=["GET"])
def camera_latest():
    if request.args.get("raw") == "1":
        if not CAMERA_PATH.exists():
            return jsonify({"available": False, "message": "Waiting for camera image"}), 404
        return send_file(CAMERA_PATH, mimetype=camera_state.get("content_type") or "image/jpeg", max_age=0)
    return jsonify({**camera_state, "online": bool(camera_state["last_capture"] and time.time() - datetime.fromisoformat(camera_state["last_capture"]).timestamp() <= CAMERA_TIMEOUT), "image_url": "/api/camera/latest?raw=1" if CAMERA_PATH.exists() else None})


@app.route("/api/risk-assessment", methods=["GET"])
def risk_assessment():
    device_id = request.args.get("device_id")
    assessment_data = latest_data_by_device.get(device_id) if device_id else latest_data
    if assessment_data is None:
        return jsonify({"available": False, "message": "Waiting for sensor data"})
    forecast_data = forecast_from_history(get_sensor_history(assessment_data.get("device_id"), 5000))
    return jsonify({"available": True, "assessment": fuse_risk(assessment_data, forecast_data, camera_state.get("vision"), assessment_data.get("edge_decision"))})


@app.route("/api/alerts", methods=["GET"])
def alerts_history():
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        return jsonify({"success": False, "message": "limit must be an integer"}), 400
    return jsonify({"success": True, "alerts": get_alerts(limit, request.args.get("device_id"))})


@app.route("/api/reports/incident", methods=["GET"])
def incident_report_api():
    report = generate_incident_report(
        device_id=request.args.get("device_id") or (latest_data or {}).get("device_id"),
        incident=request.args.get("incident"),
        severity=request.args.get("severity"),
        location=request.args.get("location"),
        start=request.args.get("start"),
        end=request.args.get("end"),
    )
    return jsonify(report)


@app.route("/api/reports/export", methods=["GET"])
def export_incident_report_api():
    export_format = (request.args.get("format") or "json").lower()
    report = generate_incident_report(
        device_id=request.args.get("device_id") or (latest_data or {}).get("device_id"),
        incident=request.args.get("incident"),
        severity=request.args.get("severity"),
        location=request.args.get("location"),
        start=request.args.get("start"),
        end=request.args.get("end"),
    )
    payload = export_incident_report(report, export_format)
    if export_format == "csv":
        mime_type = "text/csv"
        filename = "cloudguard_incident_report.csv"
    elif export_format == "pdf":
        mime_type = "application/pdf"
        filename = "cloudguard_incident_report.pdf"
    else:
        mime_type = "application/json"
        filename = "cloudguard_incident_report.json"
    return send_file(io.BytesIO(payload), mimetype=mime_type, as_attachment=True, download_name=filename)


# ============================================
# API DOCUMENTATION
# ============================================

@app.route("/docs")
def api_docs():
    backend_status = "online" if latest_data else "waiting"
    last_data_time = last_seen_by_device.get((latest_data or {}).get("device_id")) if latest_data else None
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CloudGuard Backend API Documentation</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0f4c75 0%, #1a5fa0 100%);
                color: #333;
                line-height: 1.6;
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #0f4c75 0%, #1a5fa0 100%);
                color: white;
                padding: 40px 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                font-weight: 700;
            }
            
            .header p {
                font-size: 1.1em;
                opacity: 0.95;
                font-weight: 300;
            }
            
            .status-banner {
                background: #f8f9fa;
                border-left: 5px solid #28a745;
                padding: 20px 30px;
                margin: 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .status-item {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .status-indicator {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #28a745;
            }
            
            .status-item strong {
                color: #0f4c75;
            }
            
            .status-item span {
                color: #666;
            }
            
            .content {
                padding: 40px 30px;
            }
            
            .section {
                margin-bottom: 40px;
            }
            
            .section h2 {
                color: #0f4c75;
                font-size: 1.8em;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 3px solid #0f4c75;
            }
            
            .architecture-diagram {
                background: #f8f9fa;
                border: 2px solid #0f4c75;
                border-radius: 6px;
                padding: 20px;
                font-family: 'Courier New', monospace;
                font-size: 0.95em;
                color: #0f4c75;
                line-height: 1.8;
                overflow-x: auto;
                margin-bottom: 20px;
            }
            
            .notes {
                background: #e8f4f8;
                border-left: 4px solid #0f4c75;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                font-size: 0.95em;
            }
            
            .notes strong {
                color: #0f4c75;
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }
            
            thead {
                background: #0f4c75;
                color: white;
            }
            
            th {
                padding: 15px;
                text-align: left;
                font-weight: 600;
            }
            
            td {
                padding: 12px 15px;
                border-bottom: 1px solid #e0e0e0;
            }
            
            tbody tr:hover {
                background: #f5f5f5;
                transition: background 0.2s;
            }
            
            .method-badge {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: 600;
                font-size: 0.85em;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .method-get {
                background: #e3f2fd;
                color: #1565c0;
                border: 1px solid #1565c0;
            }
            
            .method-post {
                background: #f3e5f5;
                color: #6a1b9a;
                border: 1px solid #6a1b9a;
            }
            
            .endpoint {
                font-family: 'Courier New', monospace;
                background: #f5f5f5;
                padding: 6px 10px;
                border-radius: 3px;
                font-size: 0.9em;
                color: #d32f2f;
            }
            
            .purpose {
                color: #555;
                font-size: 0.95em;
            }
            
            .footer {
                background: #f8f9fa;
                border-top: 1px solid #e0e0e0;
                padding: 20px 30px;
                text-align: center;
                color: #666;
                font-size: 0.9em;
            }
            
            .footer a {
                color: #0f4c75;
                text-decoration: none;
            }
            
            .footer a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌍 CloudGuard Backend</h1>
                <p>REST API Reference — CloudGuard Environmental Intelligence System</p>
            </div>
            
            <div class="status-banner">
                <div class="status-item">
                    <div class="status-indicator"></div>
                    <div>
                        <strong>Backend Status:</strong>
                        <span>""" + backend_status.upper() + """</span>
                    </div>
                </div>
                <div class="status-item">
                    <strong>API Version:</strong>
                    <span>4.0</span>
                </div>
            </div>
            
            <div class="content">
                <!-- ARCHITECTURE SECTION -->
                <div class="section">
                    <h2>System Architecture</h2>
                    <div class="architecture-diagram">
                        ESP32 Sensors
                           ↓
                        Edge Processing (Local Risk Calculation)
                           ↓
                        ESP32-CAM (via ESP-NOW local wireless)
                           ↓
                        Main ESP32 (Wi-Fi/HTTP Upload)
                           ↓
                        CloudGuard Backend ← You are here
                           ↓
                        AI/Risk Engine (ML Models + Risk Fusion)
                           ↓
                        Dashboard (Real-time Monitoring)
                    </div>
                    
                    <div class="notes">
                        <strong>💡 Communication Overview:</strong>
                        <br>
                        • <strong>ESP-NOW (Local Wireless):</strong> ESP32-CAM ↔ Main ESP32 (198-byte packets, 50-200ms latency)
                        <br>
                        • <strong>Wi-Fi/HTTP (Cloud):</strong> Main ESP32 → Backend (sensor data, image upload)
                        <br>
                        • <strong>Offline Operation:</strong> All sensor processing continues locally even without internet
                        <br>
                        • <strong>Risk Fusion:</strong> Combines edge risk + ML predictions + camera evidence
                    </div>
                </div>
                
                <!-- API ENDPOINTS SECTION -->
                <div class="section">
                    <h2>REST API Endpoints</h2>
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 10%;">METHOD</th>
                                <th style="width: 30%;">ENDPOINT</th>
                                <th style="width: 60%;">PURPOSE</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/</span></td>
                                <td class="purpose">Backend status</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/health</span></td>
                                <td class="purpose">Health and alert configuration</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-post">POST</span></td>
                                <td><span class="endpoint">/api/sensor-data</span></td>
                                <td class="purpose">Receive ESP32 sensor data</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/latest-data</span></td>
                                <td class="purpose">Get latest sensor reading</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/history</span></td>
                                <td class="purpose">Get historical sensor readings</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/sensor-history</span></td>
                                <td class="purpose">Get sensor history compatibility data</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/devices</span></td>
                                <td class="purpose">Get all device states</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/devices/&lt;device_id&gt;</span></td>
                                <td class="purpose">Get a specific device</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/forecast</span></td>
                                <td class="purpose">Get risk forecast</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/forecast/history</span></td>
                                <td class="purpose">Get forecast history</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-post">POST</span></td>
                                <td><span class="endpoint">/api/camera/trigger</span></td>
                                <td class="purpose">Trigger ESP32-CAM event</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-post">POST</span></td>
                                <td><span class="endpoint">/api/camera/upload</span></td>
                                <td class="purpose">Upload camera image</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/camera/latest</span></td>
                                <td class="purpose">Get latest camera information</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/risk-assessment</span></td>
                                <td class="purpose">Get combined risk assessment</td>
                            </tr>
                            <tr>
                                <td><span class="method-badge method-get">GET</span></td>
                                <td><span class="endpoint">/api/alerts</span></td>
                                <td class="purpose">Get alert history</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="footer">
                CloudGuard Environmental Monitoring System v4.0 | API Documentation
                <br>
                For more information, visit the <a href="/">backend status</a> or check the dashboard
            </div>
        </div>
    </body>
    </html>
    """
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False
    )