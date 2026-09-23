"""Pluggable camera-vision boundary.

A fire/smoke detector must be trained or explicitly configured before it can
make claims. The prototype therefore reports unavailable rather than guessing.
"""
from __future__ import annotations

import os

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def analyze_image(image_path: str, content_type: str | None = None) -> dict:
    model_path = os.getenv("CLOUDGUARD_VISION_MODEL")
    if not model_path or not os.path.exists(model_path):
        return {"vision_available": False, "vision_status": "UNAVAILABLE", "message": "Vision model is not configured; no fire or smoke claim was made"}
    return {"vision_available": False, "vision_status": "UNAVAILABLE", "message": "Configured vision adapter is not implemented for this model format"}
