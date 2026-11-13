"""Money rules. Every payment in the system is created through one of these functions."""
import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction

from apps.jobs.models import Job
from apps.jobs.services import log_event
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .gateways import GatewayError, get_gateway, normalise_phone
from .models import MpesaRequest, Payment

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """A payment problem the user should be told about."""


def _to_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise PaymentError("Enter a valid amount.")
    if amount <= 0:
        raise PaymentError("Amount must be more than zero.")
    return amount


def _notify_customer(job: Job, text: str) -> None:
    if job.customer.user_id:
        notify(job.customer.user, Notification.Type.PAYMENT, "Payment received", text, job=job, sms=True)


@transaction.atomic
def record_cash_payment(job: Job, amount, user, notes: str = "") -> Payment:
    job = Job.objects.select_for_update().get(pk=job.pk)  # lock the row so two clerks can't overpay
    amount = _to_amount(amount)
    if job.status == Job.Status.CANCELLED:
        raise PaymentError("Cannot take payment for a cancelled job.")
    if amount > job.balance_due:
        raise PaymentError(f"That is more than the balance due ({job.balance_due}).")
    payment = Payment.objects.create(job=job, amount=amount, method=Payment.Method.CASH, notes=notes, recorded_by=user)
    log_event(job, "payment_cash", f"Cash payment recorded: {amount} (balance {job.balance_due})", user, notes)
    _notify_customer(job, f"We received your cash payment of {amount} for job #{job.pk}.")
    return payment


@transaction.atomic
def record_refund(job: Job, amount, user, notes: str = "") -> Payment:
    job = Job.objects.select_for_update().get(pk=job.pk)
    amount = _to_amount(amount)
    if amount > job.amount_paid:
        raise PaymentError(f"You can refund at most {job.amount_paid}.")
    payment = Payment.objects.create(
        job=job, amount=-amount, method=Payment.Method.CASH, notes=notes or "Refund", recorded_by=user
    )
    log_event(job, "refund", f"Refund recorded: {amount}", user, notes)
    return payment


# ---------------------------------------------------------------- M-Pesa
def start_mpesa_payment(job: Job, phone: str, amount, user) -> MpesaRequest:
    amount = _to_amount(amount)
    if job.status == Job.Status.CANCELLED:
        raise PaymentError("Cannot take payment for a cancelled job.")
    if amount > job.balance_due:
        raise PaymentError(f"That is more than the balance due ({job.balance_due}).")
    try:
        phone = normalise_phone(phone)
        response = get_gateway().stk_push(
            phone=phone, amount=amount, reference=f"JOB{job.pk}", description="Car wash"
        )
    except GatewayError as exc:
        raise PaymentError(str(exc))
    request = MpesaRequest.objects.create(
        job=job, phone=phone, amount=amount,
        checkout_request_id=response.checkout_request_id, merchant_request_id=response.merchant_request_id,
    )
    log_event(job, "mpesa_requested", f"M-Pesa prompt sent to {phone} for {amount}", user)
    return request


@transaction.atomic
def handle_mpesa_result(checkout_request_id: str, result_code: int, result_desc: str = "",
                        receipt: str = "", paid_amount=None) -> MpesaRequest | None:
    """
    Called by the Safaricom callback (or by the fake-mode simulator).
    Idempotent: calling it twice for the same request changes nothing the second time.
    """
    req = MpesaRequest.objects.select_for_update().filter(checkout_request_id=checkout_request_id).first()
    if req is None:
        logger.warning("M-Pesa callback for unknown request %s", checkout_request_id)
        return None
    if req.status != MpesaRequest.Status.PENDING:
        return req  # already processed

    req.result_desc = (result_desc or "")[:255]
    if result_code != 0:
        req.status = MpesaRequest.Status.FAILED
        req.save()
        log_event(req.job, "mpesa_failed", f"M-Pesa payment failed: {req.result_desc}")
        return req

    # Trust the amount we asked for, and make sure Safaricom agrees with it.
    if paid_amount is not None and Decimal(str(paid_amount)) != req.amount:
        req.status = MpesaRequest.Status.FAILED
        req.result_desc = "Amount mismatch - flagged for manual review"
        req.save()
        logger.error("M-Pesa amount mismatch on %s", checkout_request_id)
        return req

    # Re-check balance under row lock to prevent overpayment via duplicate callbacks
    job = Job.objects.select_for_update().get(pk=req.job_id)
    if req.amount > job.balance_due:
        req.status = MpesaRequest.Status.FAILED
        req.result_desc = f"Amount exceeds balance due ({job.balance_due}) - flagged for manual review"
        req.save()
        logger.error("M-Pesa amount exceeds balance due on %s", checkout_request_id)
        return req

    try:
        with transaction.atomic():
            payment = Payment.objects.create(
                job=req.job, amount=req.amount, method=Payment.Method.MPESA,
                reference=receipt or f"FAKE{uuid.uuid4().hex[:8].upper()}", phone=req.phone,
            )
    except IntegrityError:  # same receipt seen before
        req.status = MpesaRequest.Status.FAILED
        req.result_desc = "Duplicate receipt"
        req.save()
        return req
    req.status = MpesaRequest.Status.SUCCESS
    req.payment = payment
    req.save()
    log_event(req.job, "payment_mpesa", f"M-Pesa payment received: {req.amount} ({payment.reference})")
    _notify_customer(req.job, f"We received your M-Pesa payment of {req.amount} for job #{req.job_id}.")
    return req


def parse_daraja_callback(payload: dict):
    """Pull the fields we need out of Safaricom's nested callback JSON."""
    cb = payload["Body"]["stkCallback"]
    items = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
    return {
        "checkout_request_id": cb["CheckoutRequestID"],
        "result_code": int(cb["ResultCode"]),
        "result_desc": cb.get("ResultDesc", ""),
        "receipt": str(items.get("MpesaReceiptNumber", "")),
        "paid_amount": items.get("Amount"),
    }


def fake_mode_enabled() -> bool:
    return settings.MPESA_MODE == "fake"
