"""Server-side FCM boundary.

No notification is sent unless Firebase Admin is installed, credentials are
configured outside source control, and a device token is explicitly supplied.
"""
from __future__ import annotations

import os


def send_push(title: str, body: str, token: str | None) -> dict[str, str | bool]:
    if not token:
        return {"available": False, "status": "NOT_CONFIGURED", "message": "No FCM device token supplied"}
    credential_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not credential_path:
        return {"available": False, "status": "NOT_CONFIGURED", "message": "FIREBASE_CREDENTIALS_PATH is not configured"}
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError:
        return {"available": False, "status": "NOT_INSTALLED", "message": "Firebase Admin SDK is not installed"}
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(credential_path))
        message_id = messaging.send(messaging.Message(notification=messaging.Notification(title=title, body=body), token=token))
        return {"available": True, "status": "SENT", "message_id": message_id}
    except Exception:
        return {"available": False, "status": "FAILED", "message": "FCM delivery failed; inspect server logs securely"}
