import os
import time
import uuid
from dotenv import load_dotenv
from fcm_service import send_push
from sensor_database import save_alert
from sms_service import send_sms
try:
    from twilio.rest import Client
except ImportError:
    Client = None

load_dotenv()

# ==============================
# TWILIO TRIAL
# ==============================

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
ALERT_RECIPIENTS = [value.strip() for value in os.getenv("ALERT_RECIPIENTS", "").split(",") if value.strip()]
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
_last_alerts = {}
client = Client(ACCOUNT_SID, AUTH_TOKEN) if Client and ACCOUNT_SID and AUTH_TOKEN else None


def send_alert(data, severity, message=None):
    hazard = str(data.get("hazard", "environment")).upper()
    device_id = str(data.get("device_id", "unknown"))
    severity = str(severity).upper()
    alert_id = f"{device_id}:{hazard}:{severity}"
    now = time.time()
    if now - _last_alerts.get(alert_id, 0) < ALERT_COOLDOWN_SECONDS:
        return False
    _last_alerts[alert_id] = now

    message_body = message or data.get("alert_message", f"CloudGuard {severity.lower()} {hazard} alert for node {device_id}. Preventive action recommended.")
    event_id = str(data.get("event_id") or f"{device_id}-{hazard}-{int(now)}")
    alert_id = f"{event_id}-{uuid.uuid4().hex[:8]}"
    fcm_result = {"status": "NOT_ATTEMPTED"}
    if severity in {"WARNING", "CRITICAL"}:
        fcm_result = send_push(f"CloudGuard {severity} {hazard}", message_body, data.get("fcm_token"))
    if not client or not FROM_NUMBER or not ALERT_RECIPIENTS:
        sms_delivered = send_sms(message_body)
        save_alert({"alert_id": alert_id, "event_id": event_id, "timestamp": datetime_now(), "device_id": device_id, "hazard": hazard, "severity": severity, "message": message_body, "fcm_status": fcm_result.get("status", "NOT_ATTEMPTED"), "sms_status": "SENT" if sms_delivered else "NOT_CONFIGURED"})
        return sms_delivered

    delivered = False
    for number in ALERT_RECIPIENTS:
        try:
            message_result = client.messages.create(body=message_body, from_=FROM_NUMBER, to=number)
            print("SMS sent to:", number)
            print("SID:", message_result.sid)
            delivered = True
        except Exception as error:
            print("SMS failed for", number)
            print(error)
    save_alert({"alert_id": alert_id, "event_id": event_id, "timestamp": datetime_now(), "device_id": device_id, "hazard": hazard, "severity": severity, "message": message_body, "fcm_status": fcm_result.get("status", "NOT_ATTEMPTED"), "sms_status": "SENT" if delivered else "FAILED"})
    return delivered


def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def send_critical_alert(data):
    if str(data.get("overall_status", "")).upper() != "CRITICAL":
        print("No alert - status:", data.get("overall_status"))
        return False
    return send_alert(data, "CRITICAL")


def send_forecast_alert(data, forecast):
    severity = str(forecast.get("predicted_status", "")).upper()
    if not forecast.get("forecast_available") or severity not in {"WARNING", "CRITICAL"}:
        return False
    message = f"CloudGuard Early Warning: Node {data.get('device_id', 'unknown')}. {forecast.get('message', 'Increasing environmental risk predicted within approximately 6 hours')}. Preventive action recommended."
    return send_alert({**data, "hazard": forecast.get("hazard", "environment")}, severity, message)