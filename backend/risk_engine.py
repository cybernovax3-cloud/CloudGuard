"""Transparent fusion for current, forecast, edge, and camera evidence."""
from __future__ import annotations


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status(value):
    if value >= 75:
        return "CRITICAL"
    if value >= 50:
        return "WARNING"
    if value >= 25:
        return "WATCH"
    return "NORMAL"


def fuse_risk(current: dict, forecast: dict | None = None, vision: dict | None = None, edge: dict | None = None) -> dict:
    current_risk = _number(current.get("overall_risk")) or 0.0
    forecast_risk = _number((forecast or {}).get("overall_probability")) if (forecast or {}).get("forecast_available") else None
    vision_status = str((vision or {}).get("vision_status", "UNAVAILABLE")).upper()
    vision_risk = 90.0 if vision_status == "FIRE" else 65.0 if vision_status == "SMOKE" else None
    edge_risk = _number((edge or {}).get("risk_score")) if (edge or {}).get("available") else None
    candidates = [value for value in (current_risk, forecast_risk, edge_risk, vision_risk) if value is not None]
    overall_risk = round(max(candidates), 2) if candidates else None
    hazard = "ENVIRONMENT"
    if forecast and forecast.get("forecast_available"):
        hazard = str(forecast.get("hazard", hazard)).upper()
    if vision_status in {"FIRE", "SMOKE"}:
        hazard = "FIRE"
    if edge and edge.get("evidence"):
        evidence = [f"Edge evidence: {item}" for item in edge["evidence"]]
    else:
        evidence = []
    confidence_values = [_number(current.get("current_model_confidence")), _number((forecast or {}).get("confidence")), _number((vision or {}).get("confidence"))]
    confidence_values = [value for value in confidence_values if value is not None]
    confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else None
    if current_risk:
        evidence.append(f"Current sensor risk is {current_risk:.0f}/100")
    if forecast_risk is not None:
        evidence.append(f"6-hour forecast estimates {forecast_risk:.0f}/100")
    if vision_status in {"FIRE", "SMOKE"}:
        evidence.append(f"Camera evidence: {vision_status.lower()}")
    return {"overall_risk": overall_risk, "current_risk": round(current_risk, 2), "predicted_risk": forecast_risk, "edge_risk": edge_risk, "vision_risk": vision_risk, "hazard": hazard, "confidence": confidence, "status": _status(overall_risk) if overall_risk is not None else "N/A", "evidence_sources": [source for source, present in (("current_sensor", current_risk is not None), ("forecast", forecast_risk is not None), ("edge", edge_risk is not None), ("camera", vision_risk is not None)) if present], "explanation": "; ".join(evidence) or "No risk evidence available", "recommended_action": "Immediate response recommended" if overall_risk is not None and overall_risk >= 75 else "Continue monitoring"}
