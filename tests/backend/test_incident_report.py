import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

import app as backend


def test_generate_incident_report_collects_core_fields():
    sample = {
        "device_id": "CG01",
        "overall_risk": 92,
        "rainfall": 120,
        "rain_sensor_percent": 82,
        "temperature": 31,
        "humidity": 70,
        "pressure": 1008,
        "water_level": 68,
        "water_rise": 25,
        "soil_moisture": 75,
        "tilt_change": 8,
        "vibration": True,
        "mq2_raw": 210,
        "mq2_change": 35,
        "mq135_raw": 76,
        "mq135_change": 20,
        "flood_status": "CRITICAL",
        "landslide_status": "WARNING",
        "mq2_status": "WARNING",
        "mq135_status": "WATCH",
        "overall_status": "CRITICAL",
        "timestamp": "2026-09-16T08:32:00+00:00",
    }

    backend.latest_data = sample
    backend.latest_data_by_device = {sample["device_id"]: sample}
    backend.get_sensor_history = lambda device_id=None, limit=256: [sample]
    backend.get_alerts = lambda limit=100, device_id=None: [{
        "timestamp": "2026-09-16T08:35:00+00:00",
        "hazard": "Flood",
        "severity": "CRITICAL",
        "message": "Water reached critical level in Zone A.",
    }]
    backend.get_latest_camera_event = lambda device_id=None: {
        "device_id": "CG01",
        "timestamp": "2026-09-16T08:40:00+00:00",
        "trigger_reason": "Flood indicators confirmed",
        "hazard": "Flood",
        "vision": {"vision_status": "FLOOD", "message": "Standing water and flood line visible."},
    }

    report = backend.generate_incident_report("CG01")

    assert report["incident"] == "Flood Risk"
    assert report["location"] == "Zone A"
    assert report["peak_rainfall"] == 120
    assert report["peak_water_level"] == 68
    assert report["maximum_risk"] == 92
    assert "sensor_evidence" in report
    assert "camera_evidence" in report
    assert "alert_history" in report
    assert "response_timeline" in report


def test_incident_report_exports_csv_and_json_bytes():
    report = {
        "incident": "Flood Risk",
        "location": "Zone A",
        "duration": "08:32–09:15",
        "peak_rainfall": 100,
        "peak_water_level": 60,
        "maximum_risk": 90,
        "sensor_evidence": ["Rainfall spike at 100 mm/hr"],
        "camera_evidence": ["Flood line visible"],
        "alert_history": ["Water level critical"],
        "response_timeline": ["08:35 Alert generated"],
    }

    csv_bytes = backend.export_incident_report(report, "csv")
    json_bytes = backend.export_incident_report(report, "json")

    assert isinstance(csv_bytes, (bytes, bytearray))
    assert isinstance(json_bytes, (bytes, bytearray))
    assert b"Incident: Flood Risk" in csv_bytes
    assert b'"incident"' in json_bytes
