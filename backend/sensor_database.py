"""Firebase Realtime Database storage for CloudGuard records."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from firebase_service import get_firebase_db


DEVICE_IDS = ("CG01", "CG02", "CG03", "CG04")


def initialize_database() -> None:
    """Verify that the configured Firebase database is available.

    Firebase creates paths on first write, so no production records are
    created during initialization.
    """
    get_firebase_db()


def _cloudguard_ref():
    return get_firebase_db().child("cloudguard")


def _device_ref(device_id: str):
    return _cloudguard_ref().child("devices").child(device_id)


def _as_reading(value: Any, database_id: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    reading = dict(value)
    if database_id is not None:
        reading["database_id"] = database_id
    return reading


def _timestamp_value(value: Any) -> str:
    return str(value or "")


def _sort_readings(readings: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ordered = sorted(readings, key=lambda item: _timestamp_value(item.get("timestamp")))
    return ordered[-limit:]


def _read_device_readings(device_id: str) -> list[dict[str, Any]]:
    values = _device_ref(device_id).child("readings").get() or {}
    if not isinstance(values, dict):
        return []
    return [_as_reading(value, key) for key, value in values.items() if isinstance(value, dict)]


def _read_device_latest(device_id: str) -> dict[str, Any] | None:
    value = _device_ref(device_id).child("latest").get()
    return _as_reading(value) if isinstance(value, dict) else None


def save_sensor_reading(reading: dict[str, Any]) -> str:
    device_id = str(reading["device_id"])
    device = _device_ref(device_id)
    reading_ref = device.child("readings").push()
    reading_id = reading_ref.key
    stored = dict(reading)
    reading_ref.set(stored)
    device.child("latest").set({**stored, "database_id": reading_id})
    return str(reading_id)


def get_latest_reading(device_id: str | None = None) -> dict[str, Any] | None:
    if device_id:
        return _read_device_latest(device_id)
    latest = [reading for device in DEVICE_IDS if (reading := _read_device_latest(device))]
    if not latest:
        return None
    return max(latest, key=lambda item: _timestamp_value(item.get("timestamp")))


def get_latest_readings_by_device() -> list[dict[str, Any]]:
    return sorted(
        [reading for device in DEVICE_IDS if (reading := _read_device_latest(device))],
        key=lambda item: str(item.get("device_id", "")),
    )


def get_recent_readings(limit: int = 256) -> list[dict[str, Any]]:
    return _sort_readings(
        [reading for device in DEVICE_IDS for reading in _read_device_readings(device)],
        max(1, min(int(limit), 5000)),
    )


def get_readings_for_training(limit: int = 5000) -> list[dict[str, Any]]:
    return get_recent_readings(limit)


def get_sensor_history(device_id: str | None = None, limit: int = 256) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(int(limit), 5000))
    if device_id:
        readings = _read_device_readings(device_id)
    else:
        readings = [reading for device in DEVICE_IDS for reading in _read_device_readings(device)]
    return _sort_readings(readings, bounded_limit)


def save_camera_event(event: dict[str, Any]) -> None:
    _cloudguard_ref().child("camera_events").child(event["event_id"]).set(dict(event))


def update_camera_event(event_id: str, **changes: Any) -> dict[str, Any] | None:
    allowed = {"status", "image_path", "content_type", "vision", "updated_at"}
    changes = {key: value for key, value in changes.items() if key in allowed}
    if not changes:
        return get_camera_event(event_id)
    changes.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
    _cloudguard_ref().child("camera_events").child(event_id).update(changes)
    return get_camera_event(event_id)


def get_camera_event(event_id: str) -> dict[str, Any] | None:
    value = _cloudguard_ref().child("camera_events").child(event_id).get()
    return dict(value) if isinstance(value, dict) else None


def get_latest_camera_event(device_id: str | None = None) -> dict[str, Any] | None:
    values = _cloudguard_ref().child("camera_events").get() or {}
    events = [dict(value) for value in values.values() if isinstance(value, dict)] if isinstance(values, dict) else []
    if device_id:
        events = [event for event in events if event.get("device_id") == device_id]
    return max(events, key=lambda item: _timestamp_value(item.get("timestamp"))) if events else None


def save_alert(alert: dict[str, Any]) -> None:
    _cloudguard_ref().child("alerts").child(alert["alert_id"]).set(dict(alert))


def get_alerts(limit: int = 100, device_id: str | None = None) -> list[dict[str, Any]]:
    values = _cloudguard_ref().child("alerts").get() or {}
    alerts = [dict(value) for value in values.values() if isinstance(value, dict)] if isinstance(values, dict) else []
    if device_id:
        alerts = [alert for alert in alerts if alert.get("device_id") == device_id]
    alerts.sort(key=lambda item: _timestamp_value(item.get("timestamp")), reverse=True)
    return alerts[:max(1, min(int(limit), 1000))]
