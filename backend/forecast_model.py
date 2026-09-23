"""Data-driven six-hour risk estimate using real SQLite sensor history.

This is intentionally a conservative statistical baseline, not a claim of
scientifically validated disaster prediction. It refuses to forecast without
sufficient real history.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from statistics import mean

import joblib

MIN_HISTORY_READINGS = 24
MIN_HISTORY_SECONDS = 15 * 60
HORIZON_HOURS = 6
FORECAST_MODEL_FILE = Path(__file__).resolve().parent / "cloudguard_forecast_model.joblib"
FORECAST_METADATA_FILE = Path(__file__).resolve().parent / "cloudguard_forecast_model.metadata.json"
FORECAST_FEATURES = ("rainfall", "humidity", "pressure", "water_level", "water_rise", "temperature", "soil_moisture")


def _load_ml_model():
    if not FORECAST_MODEL_FILE.exists() or not FORECAST_METADATA_FILE.exists():
        return None
    try:
        with FORECAST_METADATA_FILE.open(encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)
        if metadata.get("training_source") != "SQLite sensor_readings" or metadata.get("horizon_hours") != HORIZON_HOURS:
            return None
        return joblib.load(FORECAST_MODEL_FILE)
    except (OSError, ValueError, EOFError, json.JSONDecodeError):
        return None


_ML_MODEL = _load_ml_model()


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _time(reading):
    raw = reading.get("timestamp")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _clamp(value):
    return round(max(0.0, min(100.0, value)), 2)


def _status(value):
    if value >= 75:
        return "CRITICAL"
    if value >= 50:
        return "WARNING"
    if value >= 25:
        return "WATCH"
    return "NORMAL"


def _ml_forecast(reading: dict) -> dict | None:
    if _ML_MODEL is None:
        return None
    try:
        features = [[float(reading[field]) for field in FORECAST_FEATURES]]
        prediction = str(_ML_MODEL.predict(features)[0]).upper()
        probabilities = _ML_MODEL.predict_proba(features)[0]
        confidence = float(max(probabilities) * 100)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    risk_scores = {"NORMAL": 0.0, "WATCH": 33.33, "WARNING": 66.67, "CRITICAL": 100.0}
    return {
        "forecast_available": True,
        "horizon_hours": HORIZON_HOURS,
        "predicted_status": prediction,
        "confidence": round(confidence, 2),
        "overall_probability": risk_scores.get(prediction, 0.0),
        "hazard": "ENVIRONMENT",
        "forecast_generated_at": datetime.now(timezone.utc).isoformat(),
        "message": "Six-hour ML forecast based on future-labelled historical sensor data",
        "model_type": "ML",
    }


def _trend(values, times):
    if len(values) < 2 or times[-1] <= times[0]:
        return 0.0
    return (values[-1] - values[0]) / ((times[-1] - times[0]) / 60.0)


def forecast_from_history(readings: list[dict]) -> dict:
    if readings:
        ml_result = _ml_forecast(readings[-1])
        if ml_result is not None:
            return ml_result
    if len(readings) < MIN_HISTORY_READINGS:
        return {"forecast_available": False, "message": "Insufficient historical sensor data for 6-hour forecasting"}
    times = [_time(reading) for reading in readings]
    if any(value is None for value in times) or times[-1] - times[0] < MIN_HISTORY_SECONDS:
        return {"forecast_available": False, "message": "Insufficient historical sensor data for 6-hour forecasting"}

    rainfall = [_number(item.get("rainfall")) for item in readings]
    water = [_number(item.get("water_level")) for item in readings]
    pressure = [_number(item.get("pressure")) for item in readings]
    temperature = [_number(item.get("temperature")) for item in readings]
    soil = [_number(item.get("soil_moisture")) for item in readings]
    current = [_number(item.get("overall_risk")) for item in readings]
    flood = [_number(item.get("flood_risk")) for item in readings]
    landslide = [_number(item.get("landslide_risk")) for item in readings]
    air_gas = [_number(item.get("air_gas_risk")) for item in readings]
    horizon_minutes = HORIZON_HOURS * 60
    water_trend = _trend(water, times)
    rain_trend = _trend(rainfall, times)
    pressure_trend = _trend(pressure, times)
    temp_trend = _trend(temperature, times)
    last_risk = current[-1]

    flood_probability = _clamp(max(flood[-1], last_risk * 0.8) + max(0, water_trend) * 18 + max(0, rain_trend) * 4)
    landslide_probability = _clamp(max(landslide[-1], last_risk * 0.45) + max(0, water_trend) * 8 + max(0, -_trend(soil, times)) * 2)
    air_probability = _clamp(max(air_gas[-1], last_risk * 0.35) + max(0, temp_trend) * 3 + max(0, -pressure_trend) * 1.2)
    fire_probability = _clamp(last_risk * 0.5 + max(0, temp_trend) * 4 + max(0, -_trend(rainfall, times)) * 2)
    overall_probability = _clamp(max(flood_probability, landslide_probability, air_probability, fire_probability, last_risk) + max(0, water_trend) * 4)
    values = {"flood_probability": flood_probability, "landslide_probability": landslide_probability, "air_gas_probability": air_probability, "fire_probability": fire_probability, "overall_probability": overall_probability}
    hazard = max(values, key=values.get).replace("_probability", "").upper()
    confidence = _clamp(45 + min(35, len(readings) / 4) + min(15, (times[-1] - times[0]) / 3600 * 5))
    return {"forecast_available": True, "horizon_hours": HORIZON_HOURS, **values, "predicted_status": _status(overall_probability), "confidence": confidence, "hazard": hazard, "forecast_generated_at": datetime.now(timezone.utc).isoformat(), "message": f"Historical trend baseline estimates {hazard.lower()} risk within the next 6 hours", "model_type": "historical trend baseline"}
