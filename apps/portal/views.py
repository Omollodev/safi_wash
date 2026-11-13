"""
Customer self-service portal.

SECURITY NOTE for students: every query here starts from `request.user`'s own
Customer record (e.g. customer.jobs, customer.vehicles). That is what stops
customer A from opening customer B's job by changing the number in the URL
(an "IDOR" bug). Never fetch by pk alone in a customer-facing view.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts import services as account_services
from apps.accounts.forms import CustomerSignupForm
from apps.catalog.models import Service
from apps.core.forms import BootstrapForm, BootstrapModelForm
from apps.core.permissions import customer_required
from apps.customers.forms import PortalVehicleForm
from apps.customers.models import Customer
from apps.customers.services import ensure_customer_for_user
from apps.jobs import selectors as job_selectors
from apps.jobs import services as job_services
from apps.jobs.services import JobError
from apps.payments.services import fake_mode_enabled

User = get_user_model()


class PortalBookingForm(BootstrapForm):
    vehicle = forms.ModelChoiceField(queryset=None)
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(is_active=True), widget=forms.CheckboxSelectMultiple
    )
    special_instructions = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, customer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = customer.vehicles.filter(is_active=True)
        self.fields["services"].widget.attrs["class"] = ""


class PortalProfileForm(BootstrapModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "phone_secondary", "address", "service_preferences"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2}), "service_preferences": forms.Textarea(attrs={"rows": 2})}


def _customer(request) -> Customer:
    return ensure_customer_for_user(request.user)


# ---------------------------------------------------------------- sign-up
def signup(request):
    if request.user.is_authenticated:
        return redirect("portal:home")
    form = CustomerSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.role = User.Role.CUSTOMER  # forced here, never trusted from the form
            user.is_active = False  # must verify email first
            user.save()
            ensure_customer_for_user(user)
        account_services.send_verification_email(request, user)
        return render(request, "portal/verification_pending.html", {"email": user.email})
    return render(request, "portal/signup.html", {"form": form})


# ---------------------------------------------------------------- logged-in customer
@customer_required
def home(request):
    customer = _customer(request)
    jobs = job_selectors.jobs_for_customer(customer)
    return render(
        request,
        "portal/home.html",
        {
            "customer": customer,
            "vehicles": customer.vehicles.filter(is_active=True),
            "active_jobs": jobs.filter(status__in=job_selectors.ACTIVE_STATUSES),
            "past_jobs": jobs.filter(status__in=["completed", "cancelled"])[:10],
        },
    )


@customer_required
def profile(request):
    customer = _customer(request)
    form = PortalProfileForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("portal:home")
    return render(request, "portal/profile.html", {"form": form})


@customer_required
def vehicle_add(request):
    customer = _customer(request)
    form = PortalVehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.customer = customer
        vehicle.save()
        messages.success(request, f"{vehicle.plate_number} added.")
        return redirect("portal:home")
    return render(request, "portal/vehicle_form.html", {"form": form})


@customer_required
def book(request):
    customer = _customer(request)
    if not customer.vehicles.filter(is_active=True).exists():
        messages.info(request, "Add a vehicle first, then book a wash.")
        return redirect("portal:vehicle_add")
    form = PortalBookingForm(customer, request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            job = job_services.create_job(
                customer=customer, vehicle=d["vehicle"], services=list(d["services"]),
                created_by=request.user, special_instructions=d["special_instructions"],
            )
        except JobError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Booked! Your queue number today is #{job.queue_number}.")
            return redirect("portal:job_detail", pk=job.pk)
    return render(request, "portal/book.html", {"form": form})


@customer_required
def job_detail(request, pk):
    customer = _customer(request)
    job = get_object_or_404(job_selectors.jobs_for_customer(customer), pk=pk)  # <- ownership check
    return render(
        request,
        "portal/job_detail.html",
        {
            "job": job,
            "lines": job.job_services.select_related("service"),
            "events": job.events.exclude(kind="edited"),
            "payments": job.payments.all(),
            "fake_mode": fake_mode_enabled(),
            "mpesa": job.mpesa_requests.filter(pk=request.GET.get("mpesa") or 0).first(),
            "default_phone": customer.phone,
        },
    )
