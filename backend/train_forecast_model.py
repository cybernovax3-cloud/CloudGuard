"""Train a genuine six-hour future-risk classifier from SQLite history.

Each target is derived only from readings strictly after the feature timestamp
and within the next six hours. The script refuses to train when the temporal
history or class distribution is insufficient.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score

from sensor_database import get_readings_for_training

LOGGER = logging.getLogger("cloudguard.train_forecast_model")
BACKEND_DIR = Path(__file__).resolve().parent
MODEL_FILE = BACKEND_DIR / "cloudguard_forecast_model.joblib"
METADATA_FILE = BACKEND_DIR / "cloudguard_forecast_model.metadata.json"
HORIZON_SECONDS = 6 * 60 * 60
LABELS = ("NORMAL", "WATCH", "WARNING", "CRITICAL")
LABEL_RANK = {label: index for index, label in enumerate(LABELS)}
FEATURES = ("rainfall", "humidity", "pressure", "water_level", "water_rise", "temperature", "soil_moisture")
MIN_ROWS_PER_CLASS = 20


def _time(reading: dict[str, Any]) -> float | None:
    try:
        return datetime.fromisoformat(str(reading["timestamp"]).replace("Z", "+00:00")).timestamp()
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _number(reading: dict[str, Any], field: str) -> float | None:
    try:
        value = float(reading[field])
    except (KeyError, TypeError, ValueError):
        return None
    return value if value == value else None


def build_future_dataset(readings: list[dict[str, Any]]) -> tuple[list[list[float]], list[str], list[str]]:
    by_device: dict[str, list[dict[str, Any]]] = {}
    for reading in readings:
        timestamp = _time(reading)
        status = str(reading.get("overall_status", "")).upper()
        values = [_number(reading, field) for field in FEATURES]
        if timestamp is None or status not in LABELS or any(value is None for value in values):
            continue
        by_device.setdefault(str(reading.get("device_id", "")), []).append(reading)

    features: list[list[float]] = []
    targets: list[str] = []
    timestamps: list[str] = []
    for device_readings in by_device.values():
        ordered = sorted(device_readings, key=_time)
        for index, current in enumerate(ordered):
            current_time = _time(current)
            future = [
                item for item in ordered[index + 1:]
                if current_time < _time(item) <= current_time + HORIZON_SECONDS
            ]
            if not future:
                continue
            future_status = max(
                (str(item["overall_status"]).upper() for item in future),
                key=lambda status: LABEL_RANK[status],
            )
            features.append([float(current[field]) for field in FEATURES])
            targets.append(future_status)
            timestamps.append(str(current["timestamp"]))
    order = sorted(range(len(timestamps)), key=lambda item: timestamps[item])
    return [features[item] for item in order], [targets[item] for item in order], [timestamps[item] for item in order]


def _metrics(model, features, targets):
    predictions = model.predict(features)
    return {
        "accuracy": round(float(accuracy_score(targets, predictions)), 4),
        "precision_macro": round(float(precision_score(targets, predictions, labels=list(LABELS), average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(targets, predictions, labels=list(LABELS), average="macro", zero_division=0)), 4),
        "f1_macro": round(float(f1_score(targets, predictions, labels=list(LABELS), average="macro", zero_division=0)), 4),
        "critical_recall": round(float(recall_score(targets, predictions, labels=["CRITICAL"], average="macro", zero_division=0)), 4),
        "confusion_matrix_labels": list(LABELS),
        "confusion_matrix": confusion_matrix(targets, predictions, labels=list(LABELS)).tolist(),
        "classification_report": classification_report(targets, predictions, labels=list(LABELS), output_dict=True, zero_division=0),
        "rows": len(targets),
    }


def train() -> dict[str, Any]:
    features, targets, timestamps = build_future_dataset(get_readings_for_training(5000))
    distribution = {label: Counter(targets).get(label, 0) for label in LABELS}
    if len(targets) < MIN_ROWS_PER_CLASS * len(LABELS) or any(value < MIN_ROWS_PER_CLASS for value in distribution.values()):
        raise RuntimeError(
            "Training aborted: insufficient real future-labelled sensor history. "
            f"usable_rows={len(targets)}, class_distribution={distribution}, "
            f"minimum={MIN_ROWS_PER_CLASS}_rows_per_class."
        )
    train_end = int(len(targets) * 0.70)
    validation_end = int(len(targets) * 0.85)
    if train_end <= 0 or validation_end <= train_end or validation_end >= len(targets):
        raise RuntimeError("Training aborted: insufficient rows for chronological split")
    train_features, train_targets = features[:train_end], targets[:train_end]
    validation_features, validation_targets = features[train_end:validation_end], targets[train_end:validation_end]
    test_features, test_targets = features[validation_end:], targets[validation_end:]
    if set(LABELS) - set(train_targets):
        raise RuntimeError("Training aborted: training period does not contain every forecast class")

    model = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_leaf=2, class_weight="balanced", random_state=42, n_jobs=-1)
    model.fit(train_features, train_targets)
    metadata = {
        "model_version": "six-hour-forecast-rf-v1",
        "training_source": "SQLite sensor_readings",
        "target": "maximum recorded overall_status in the strictly future six-hour window",
        "horizon_hours": 6,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_names": list(FEATURES),
        "classes": list(LABELS),
        "sample_count": len(targets),
        "class_distribution": distribution,
        "periods": {"train": [timestamps[0], timestamps[train_end - 1]], "validation": [timestamps[train_end], timestamps[validation_end - 1]], "test": [timestamps[validation_end], timestamps[-1]]},
        "validation_metrics": _metrics(model, validation_features, validation_targets),
        "test_metrics": _metrics(model, test_features, test_targets),
    }
    temporary_model = None
    temporary_metadata = None
    try:
        with tempfile.NamedTemporaryFile(dir=BACKEND_DIR, suffix=".joblib", delete=False) as model_file:
            temporary_model = Path(model_file.name)
        joblib.dump(model, temporary_model)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=BACKEND_DIR, suffix=".json", delete=False) as metadata_file:
            temporary_metadata = Path(metadata_file.name)
            json.dump(metadata, metadata_file, indent=2)
        os.replace(temporary_model, MODEL_FILE)
        os.replace(temporary_metadata, METADATA_FILE)
    finally:
        if temporary_model and temporary_model.exists():
            temporary_model.unlink()
        if temporary_metadata and temporary_metadata.exists():
            temporary_metadata.unlink()
    return metadata


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        print(json.dumps(train(), indent=2))
    except (RuntimeError, ValueError) as error:
        print(str(error))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
