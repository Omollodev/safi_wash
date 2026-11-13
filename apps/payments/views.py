import hmac
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.permissions import staff_required
from apps.jobs.models import Job

from . import services
from .models import MpesaRequest
from .services import PaymentError

logger = logging.getLogger(__name__)


def _can_pay_for(user, job: Job) -> bool:
    """Staff can take payment for any job; a customer only for their own."""
    return user.is_staff_role or (user.is_customer and job.customer.user_id == user.pk)


def _back(request, job):
    return redirect("portal:job_detail" if request.user.is_customer else "jobs:detail", pk=job.pk)


@staff_required
@require_POST
def cash_payment(request, job_pk):
    job = get_object_or_404(Job, pk=job_pk)
    try:
        services.record_cash_payment(job, request.POST.get("amount"), request.user, request.POST.get("notes", ""))
        messages.success(request, "Cash payment recorded.")
    except PaymentError as exc:
        messages.error(request, str(exc))
    return redirect("jobs:detail", pk=job.pk)


@staff_required
@require_POST
def refund(request, job_pk):
    job = get_object_or_404(Job, pk=job_pk)
    try:
        services.record_refund(job, request.POST.get("amount"), request.user, request.POST.get("notes", ""))
        messages.success(request, "Refund recorded.")
    except PaymentError as exc:
        messages.error(request, str(exc))
    return redirect("jobs:detail", pk=job.pk)


@login_required
@require_POST
def mpesa_start(request, job_pk):
    job = get_object_or_404(Job, pk=job_pk)
    if not _can_pay_for(request.user, job):
        raise Http404  # don't reveal that the job exists
    try:
        mpesa = services.start_mpesa_payment(job, request.POST.get("phone", ""), request.POST.get("amount"), request.user)
    except PaymentError as exc:
        messages.error(request, str(exc))
        return _back(request, job)
    if services.fake_mode_enabled():
        messages.info(request, "Demo mode: no real prompt was sent. Use the 'Simulate payment' button below.")
    else:
        messages.success(request, "Check your phone and enter your M-Pesa PIN.")
    return redirect(f"{_back(request, job).url}?mpesa={mpesa.pk}")


@login_required
def mpesa_status(request, pk):
    mpesa = get_object_or_404(MpesaRequest.objects.select_related("job__customer"), pk=pk)
    if not _can_pay_for(request.user, mpesa.job):
        raise Http404
    return JsonResponse({"status": mpesa.status, "description": mpesa.result_desc})


@login_required
@require_POST
def mpesa_simulate(request, pk):
    """Fake mode only: pretend the customer typed their PIN (success) or cancelled."""
    if not services.fake_mode_enabled():
        raise Http404
    mpesa = get_object_or_404(MpesaRequest.objects.select_related("job__customer"), pk=pk)
    if not _can_pay_for(request.user, mpesa.job):
        raise Http404
    ok = request.POST.get("outcome") != "fail"
    services.handle_mpesa_result(
        mpesa.checkout_request_id, 0 if ok else 1032, "Simulated" if ok else "Request cancelled by user",
        paid_amount=mpesa.amount if ok else None,
    )
    messages.success(request, "Payment simulated." if ok else "Payment cancelled.")
    return _back(request, mpesa.job)


@csrf_exempt  # Safaricom's servers cannot send a CSRF token; we authenticate with a secret URL token instead.
@require_POST
def mpesa_callback(request, token):
    expected = settings.MPESA_CALLBACK_TOKEN
    if not expected or not hmac.compare_digest(token, expected):
        raise Http404
    try:
        fields = services.parse_daraja_callback(json.loads(request.body))
    except (ValueError, KeyError, TypeError):
        logger.warning("Malformed M-Pesa callback")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Bad payload"}, status=400)
    services.handle_mpesa_result(**fields)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
