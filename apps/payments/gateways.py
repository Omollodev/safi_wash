"""
M-Pesa gateways.

FakeGateway   - no network. Lets students build and demo the full payment flow.
DarajaGateway - real Safaricom Daraja STK Push (sandbox or production).

Pick one with MPESA_MODE in your .env. The rest of the code only talks to the
small interface below (`stk_push`), so adding another provider is easy.
"""
import base64
import logging
import uuid
from dataclasses import dataclass

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    pass


@dataclass
class StkResponse:
    checkout_request_id: str
    merchant_request_id: str


def normalise_phone(phone: str) -> str:
    """0712345678 / +254712345678 / 254712345678  ->  254712345678"""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    if digits.startswith("254") and len(digits) == 12:
        return digits
    raise GatewayError("Enter a valid Safaricom number like 0712345678.")


class FakeGateway:
    def stk_push(self, *, phone, amount, reference, description) -> StkResponse:
        return StkResponse(f"ws_CO_FAKE_{uuid.uuid4().hex[:16]}", f"fake-{uuid.uuid4().hex[:8]}")


class DarajaGateway:
    def __init__(self):
        self.base = (
            "https://sandbox.safaricom.co.ke" if settings.MPESA_MODE == "sandbox" else "https://api.safaricom.co.ke"
        )

    def _token(self) -> str:
        try:
            r = requests.get(
                f"{self.base}/oauth/v1/generate?grant_type=client_credentials",
                auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
                timeout=15,
            )
            r.raise_for_status()
            return r.json()["access_token"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.exception("Daraja auth failed")
            raise GatewayError("Could not reach M-Pesa. Try again shortly.") from exc

    def stk_push(self, *, phone, amount, reference, description) -> StkResponse:
        if not (settings.MPESA_CONSUMER_KEY and settings.MPESA_PASSKEY and settings.MPESA_CALLBACK_BASE_URL):
            raise GatewayError("M-Pesa is not configured. See .env.example.")
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()).decode()
        callback = settings.MPESA_CALLBACK_BASE_URL.rstrip("/") + reverse(
            "payments:mpesa_callback", args=[settings.MPESA_CALLBACK_TOKEN]
        )
        body = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),  # Daraja only accepts whole shillings
            "PartyA": phone,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": callback,
            "AccountReference": reference[:12],
            "TransactionDesc": description[:13],
        }
        try:
            r = requests.post(
                f"{self.base}/mpesa/stkpush/v1/processrequest",
                json=body, headers={"Authorization": f"Bearer {self._token()}"}, timeout=20,
            )
            data = r.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception("STK push failed")
            raise GatewayError("Could not start the M-Pesa payment.") from exc
        if data.get("ResponseCode") != "0":
            raise GatewayError(data.get("errorMessage") or data.get("ResponseDescription") or "M-Pesa refused the request.")
        return StkResponse(data["CheckoutRequestID"], data.get("MerchantRequestID", ""))


def get_gateway():
    return FakeGateway() if settings.MPESA_MODE == "fake" else DarajaGateway()
