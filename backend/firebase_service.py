"""Lazy Firebase Admin SDK access for CloudGuard services."""
from __future__ import annotations

import os

from dotenv import load_dotenv


class FirebaseConfigurationError(RuntimeError):
    """Raised when Firebase configuration is missing or incomplete."""


load_dotenv()


def get_firebase_db():
    """Initialize Firebase on demand and return the Realtime Database root."""
    credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
    database_url = os.getenv("FIREBASE_DATABASE_URL", "").strip()
    missing = []
    if not credentials_path:
        missing.append("FIREBASE_CREDENTIALS_PATH")
    if not database_url:
        missing.append("FIREBASE_DATABASE_URL")
    if missing:
        raise FirebaseConfigurationError(
            "Missing Firebase configuration: " + ", ".join(missing)
        )

    try:
        import firebase_admin
        from firebase_admin import credentials, db
    except ImportError as error:
        raise FirebaseConfigurationError(
            "Firebase Admin SDK is not installed; install firebase-admin"
        ) from error

    if firebase_admin._apps:
        app = firebase_admin.get_app()
    else:
        certificate = credentials.Certificate(credentials_path)
        app = firebase_admin.initialize_app(certificate, {"databaseURL": database_url})
    return db.reference("/", app=app)