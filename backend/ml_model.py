"""Current-risk model training and inference.

Training is deliberately data-gated: only validated readings already stored in
SQLite may be used, and the model is unavailable until there is enough real,
labelled data for a meaningful holdout evaluation.
"""
from __future__ import annotations

import logging
import json
import os
from collections import Counter
from typing import Any

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from sensor_database import get_readings_for_training


MODEL_FILE = os.path.join(os.path.dirname(__file__), "cloudguard_model.joblib")
MODEL_METADATA_FILE = os.path.join(os.path.dirname(__file__), "cloudguard_model.metadata.json")
logger = logging.getLogger(__name__)

FEATURES = ("rainfall", "humidity", "pressure", "water_level")
LABELS = {"NORMAL": 0, "WATCH": 1, "WARNING": 2, "CRITICAL": 3}
LABEL_NAMES = {value: key for key, value in LABELS.items()}
MIN_ROWS_PER_CLASS = 20
MIN_TRAINING_ROWS = MIN_ROWS_PER_CLASS * len(LABELS)


class TrainingDataUnavailable(RuntimeError):
    """Raised when real SQLite history is not ready for model training."""


def _training_data() -> tuple[list[list[float]], list[int]]:
    readings = get_readings_for_training()
    features: list[list[float]] = []
    targets: list[int] = []

    for reading in readings:
        label = LABELS.get(str(reading.get("overall_status", "")).upper())
        if label is None:
            continue
        try:
            row = [float(reading[name]) for name in FEATURES]
        except (KeyError, TypeError, ValueError):
            continue
        features.append(row)
        targets.append(label)

    counts = Counter(targets)
    missing = [LABEL_NAMES[label] for label in LABEL_NAMES if counts[label] < MIN_ROWS_PER_CLASS]
    if len(features) < MIN_TRAINING_ROWS or missing:
        detail = ", ".join(
            f"{LABEL_NAMES[label]}={counts[label]} (need {MIN_ROWS_PER_CLASS})"
            for label in LABEL_NAMES
        )
        raise TrainingDataUnavailable(
            "Insufficient real labelled SQLite data for current-risk training: "
            f"{len(features)} valid rows found (need {MIN_TRAINING_ROWS}); {detail}."
        )
    return features, targets


def train_model():
    X, y = _training_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=50,
        max_depth=5,
        random_state=42
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    evaluation = {
        "accuracy": round(accuracy_score(y_test, predictions), 4),
        "macro_f1": round(f1_score(y_test, predictions, average="macro", zero_division=0), 4),
        "test_rows": len(y_test),
    }

    joblib.dump(model, MODEL_FILE)
    with open(MODEL_METADATA_FILE, "w", encoding="utf-8") as metadata_file:
        json.dump({
            "training_source": "SQLite sensor_readings",
            "features": list(FEATURES),
            "labels": list(LABELS),
            "training_rows": len(y),
            "evaluation": evaluation,
        }, metadata_file, indent=2)
    logger.info("CloudGuard current-risk model trained and evaluated: %s", evaluation)

    return model


def load_model():
    if not os.path.exists(MODEL_FILE) or not os.path.exists(MODEL_METADATA_FILE):
        logger.info("No provenance-verified current-risk model is available")
        return None
    try:
        with open(MODEL_METADATA_FILE, encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)
        if metadata.get("training_source") != "SQLite sensor_readings":
            logger.warning("Ignoring current-risk model with unverified training source")
            return None
        return joblib.load(MODEL_FILE)
    except (OSError, ValueError, EOFError, json.JSONDecodeError) as exc:
        logger.warning("Current-risk model could not be loaded: %s", exc)
        return None


model = load_model()


def predict_risk(rainfall, humidity, pressure, water_level):

    if model is None:
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "confidence": None,
            "message": "Current-risk ML model is unavailable; collect sufficient real labelled SQLite data before training",
        }

    features = [[
        rainfall,
        humidity,
        pressure,
        water_level
    ]]

    prediction = model.predict(features)[0]

    probabilities = model.predict_proba(features)[0]

    confidence = max(probabilities) * 100

    status = LABEL_NAMES.get(int(prediction), "UNAVAILABLE")

    return {
        "available": True,
        "status": status,
        "confidence": float(round(confidence, 2))
    }