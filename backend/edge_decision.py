"""Small deterministic edge-risk decision engine.

The functions use only the current reading and optional previous reading, so
the same logic can be ported to ESP32 firmware without cloud connectivity.
This is threshold/anomaly logic, not a trained ML model.
"""
from __future__ import annotations

from typing import Any

STATUS_THRESHOLDS = ((75.0, "CRITICAL"), (50.0, "WARNING"), (25.0, "WATCH"))


def _number(reading: dict[str, Any], field: str) -> float | None:
    try:
        value = float(reading.get(field))
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _status(score: float) -> str:
    for threshold, status in STATUS_THRESHOLDS:
        if score >= threshold:
            return status
    return "NORMAL"


def assess_edge_risk(current: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    score = 0.0
    evidence: list[str] = []
    water = _number(current, "water_level")
    water_before = _number(previous or {}, "water_level")
    rainfall = _number(current, "rainfall")
    pressure = _number(current, "pressure")
    pressure_before = _number(previous or {}, "pressure")
    gas_change = max(_number(current, "mq2_change") or 0.0, _number(current, "mq135_change") or 0.0)
    tilt = abs(_number(current, "tilt_change") or 0.0)
    vibration = bool(current.get("vibration"))

    if water is not None and water >= 100:
        score += 55
        evidence.append("high water level")
    if water is not None and water_before is not None and water - water_before >= 5:
        score += 35
        evidence.append("rapid water-level rise")
    if rainfall is not None and rainfall >= 75:
        score += 25
        evidence.append("heavy rainfall")
    if pressure is not None and pressure_before is not None and pressure_before - pressure >= 8:
        score += 20
        evidence.append("rapid pressure drop")
    if gas_change >= 50:
        score += 30
        evidence.append("rapid gas increase")
    if tilt >= 15 or vibration:
        score += 25
        evidence.append("tilt or vibration anomaly")

    score = min(100.0, score)
    return {
        "available": True,
        "model_type": "edge threshold and rate-of-change decision",
        "risk_score": round(score, 2),
        "status": _status(score),
        "local_alert_required": score >= 75,
        "evidence": evidence,
        "message": "; ".join(evidence) if evidence else "No edge anomaly detected",
    }
