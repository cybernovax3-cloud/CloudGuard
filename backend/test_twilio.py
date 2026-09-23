import os

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
TO_NUMBER = os.getenv("TWILIO_TEST_RECIPIENT")

required_settings = {
    "TWILIO_ACCOUNT_SID": ACCOUNT_SID,
    "TWILIO_AUTH_TOKEN": AUTH_TOKEN,
    "TWILIO_FROM_NUMBER": FROM_NUMBER,
    "TWILIO_TEST_RECIPIENT": TO_NUMBER,
}
missing_settings = [name for name, value in required_settings.items() if not value]
if missing_settings:
    raise SystemExit(
        "SMS test not run; configure environment variables: "
        + ", ".join(missing_settings)
    )

client = Client(ACCOUNT_SID, AUTH_TOKEN)


# ============================================
# SEND TRIAL TEST SMS
# ============================================

try:

    message = client.messages.create(
        body="sms_internal_alerts",
        from_=FROM_NUMBER,
        to=TO_NUMBER
    )

    print()
    print("==============================")
    print("SMS SENT SUCCESSFULLY")
    print("==============================")
    print("Message SID:", message.sid)

except Exception:

    print()
    print("==============================")
    print("SMS FAILED")
    print("==============================")
    print("The SMS provider rejected the test request; inspect provider logs securely.")