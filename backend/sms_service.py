import os
from dotenv import load_dotenv

load_dotenv()


def send_sms(message):

    provider = os.getenv("SMS_PROVIDER", "console")

    phone = os.getenv("ALERT_PHONE")

    if not phone:
        print("⚠️ ALERT_PHONE not configured")
        return False

    # --------------------------------
    # DEVELOPMENT MODE
    # --------------------------------

    if provider == "console":

        print("\n================================")
        print("🚨 CLOUDGUARD SMS ALERT")
        print("TO: configured recipient (number withheld)")
        print(message)
        print("================================\n")

        return True

    # --------------------------------
    # PROVIDER INTEGRATION
    # --------------------------------

    print("SMS provider configured:", provider)

    # Add your chosen SMS provider here.

    return False