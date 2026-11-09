"""Optional SMS through Africa's Talking. Does nothing unless SMS_ENABLED=True."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def normalise_kenyan_number(phone: str) -> str:
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        return phone
    if phone.startswith("254"):
        return "+" + phone
    if phone.startswith("0") and len(phone) == 10:
        return "+254" + phone[1:]
    return phone


def send_sms(phone: str, message: str) -> bool:
    if not settings.SMS_ENABLED or not settings.AT_API_KEY or not phone:
        return False
    host = "api.sandbox.africastalking.com" if settings.AT_USERNAME == "sandbox" else "api.africastalking.com"
    data = {"username": settings.AT_USERNAME, "to": normalise_kenyan_number(phone), "message": message}
    if settings.AT_SENDER_ID:
        data["from"] = settings.AT_SENDER_ID
    try:
        response = requests.post(
            f"https://{host}/version1/messaging",
            data=data,
            headers={"apiKey": settings.AT_API_KEY, "Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        # Never let a failed SMS break a payment or a job update.
        logger.exception("SMS sending failed")
        return False
