"""Train the current-risk classifier from real SQLite sensor history.

This command never creates synthetic data and never replaces the deployed model
unless chronological evaluation succeeds. The recorded overall_status is used
as the target because it is the current node decision persisted with the
reading; it is not treated as an independent scientific ground truth.
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
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from sensor_database import get_readings_for_training

LOGGER = logging.getLogger("cloudguard.train_current_risk")
BACKEND_DIR = Path(__file__).resolve().parent
MODEL_FILE = BACKEND_DIR / "cloudguard_model.joblib"
METADATA_FILE = BACKEND_DIR / "cloudguard_model.metadata.json"
LABELS = ("NORMAL", "WATCH", "WARNING", "CRITICAL")
BASE_FEATURES = (
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
)
DELTA_FIELDS = (
    "rainfall",
    "water_level",
    "pressure",
    "temperature",
    "soil_moisture",
    "mq2_raw",
    "mq135_raw",
)
MIN_ROWS_PER_CLASS = 30
MIN_TOTAL_ROWS = MIN_ROWS_PER_CLASS * len(LABELS)


def _timestamp(reading: dict[str, Any]) -> float | None:
    raw = reading.get("timestamp")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _number(reading: dict[str, Any], field: str) -> float | None:
    value = reading.get(field)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def build_dataset(readings: list[dict[str, Any]]) -> tuple[list[list[float]], list[str], list[str]]:
    ordered = sorted(
        (reading for reading in readings if _timestamp(reading) is not None),
        key=lambda reading: (_timestamp(reading), str(reading.get("device_id", ""))),
    )
    feature_names = list(BASE_FEATURES) + [f"{field}_change" for field in DELTA_FIELDS]
    features: list[list[float]] = []
    targets: list[str] = []
    timestamps: list[str] = []
    previous_by_device: dict[str, dict[str, float]] = {}

    for reading in ordered:
        target = str(reading.get("overall_status", "")).upper()
        device_id = str(reading.get("device_id", ""))
        base_values = [_number(reading, field) for field in BASE_FEATURES]
        if target not in LABELS or any(value is None for value in base_values):
            continue
        previous = previous_by_device.get(device_id)
        if previous is None:
            previous_by_device[device_id] = {
                field: float(reading[field]) for field in BASE_FEATURES
            }
            continue
        delta_values = [float(reading[field]) - previous[field] for field in DELTA_FIELDS]
        features.append([float(value) for value in base_values] + delta_values)
        targets.append(target)
        timestamps.append(str(reading["timestamp"]))
        previous_by_device[device_id] = {
            field: float(reading[field]) for field in BASE_FEATURES
        }
    return features, targets, timestamps


def _class_distribution(targets: list[str]) -> dict[str, int]:
    counts = Counter(targets)
    return {label: counts.get(label, 0) for label in LABELS}


def _split(features: list[list[float]], targets: list[str], timestamps: list[str]):
    first_cut = int(len(targets) * 0.70)
    second_cut = int(len(targets) * 0.85)
    if first_cut <= 0 or second_cut <= first_cut or second_cut >= len(targets):
        raise ValueError("Insufficient rows for chronological train/validation/test split")
    return (
        features[:first_cut], targets[:first_cut], timestamps[:first_cut],
        features[first_cut:second_cut], targets[first_cut:second_cut], timestamps[first_cut:second_cut],
        features[second_cut:], targets[second_cut:], timestamps[second_cut:],
    )


def _evaluate(model, features: list[list[float]], targets: list[str]) -> dict[str, Any]:
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
    readings = get_readings_for_training(5000)
    features, targets, timestamps = build_dataset(readings)
    distribution = _class_distribution(targets)
    if len(targets) < MIN_TOTAL_ROWS or any(count < MIN_ROWS_PER_CLASS for count in distribution.values()):
        raise RuntimeError(
            "Training aborted: insufficient real sensor history. "
            f"usable_rows={len(targets)}, class_distribution={distribution}, "
            f"minimum={MIN_ROWS_PER_CLASS}_rows_per_class."
        )

    split = _split(features, targets, timestamps)
    train_features, train_targets, train_period = split[0:3]
    validation_features, validation_targets, validation_period = split[3:6]
    test_features, test_targets, test_period = split[6:9]
    if set(LABELS) - set(train_targets):
        raise RuntimeError("Training aborted: chronological training split does not contain every risk class")

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train_features, train_targets)
    validation_metrics = _evaluate(model, validation_features, validation_targets)
    test_metrics = _evaluate(model, test_features, test_targets)
    metadata = {
        "model_version": "current-risk-rf-v1",
        "training_source": "SQLite sensor_readings",
        "target": "recorded overall_status",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_names": list(BASE_FEATURES) + [f"{field}_change" for field in DELTA_FIELDS],
        "classes": list(LABELS),
        "sample_count": len(targets),
        "class_distribution": distribution,
        "periods": {
            "train": [train_period[0], train_period[-1]],
            "validation": [validation_period[0], validation_period[-1]],
            "test": [test_period[0], test_period[-1]],
        },
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
    }

    with tempfile.NamedTemporaryFile(dir=BACKEND_DIR, suffix=".joblib", delete=False) as model_file:
        temporary_model = Path(model_file.name)
    temporary_metadata = None
    try:
        joblib.dump(model, temporary_model)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=BACKEND_DIR, suffix=".json", delete=False) as metadata_file:
            json.dump(metadata, metadata_file, indent=2)
            temporary_metadata = Path(metadata_file.name)
        os.replace(temporary_model, MODEL_FILE)
        os.replace(temporary_metadata, METADATA_FILE)
    finally:
        if temporary_model.exists():
            temporary_model.unlink()
        if temporary_metadata and temporary_metadata.exists():
            temporary_metadata.unlink()
    LOGGER.info("Current-risk model trained and evaluated: test_metrics=%s", test_metrics)
    return metadata


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        metadata = train()
    except (RuntimeError, ValueError) as error:
        print(str(error))
        return 2
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
