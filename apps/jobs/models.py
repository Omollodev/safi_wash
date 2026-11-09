"""
Data model for jobs.

Rule of thumb used across this project:
  * models.py   -> what the data IS (fields, tiny helper properties)
  * services.py -> what HAPPENS (create a job, change status, take payment)
  * selectors.py-> how we READ (filtered/annotated queries)
  * views.py    -> glue between HTTP and the three above
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Job(TimeStampedModel):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        IN_PROGRESS = "in_progress", "In progress"
        AWAITING_EXTRA = "awaiting_extra", "Awaiting extra services"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    # The whole workflow in one dictionary: from-status -> statuses it may move to.
    ALLOWED_TRANSITIONS = {
        "waiting": ["in_progress", "cancelled"],
        "in_progress": ["awaiting_extra", "completed", "cancelled"],
        "awaiting_extra": ["in_progress", "completed"],
        "completed": [],
        "cancelled": [],
    }
    BADGES = {
        "waiting": "bg-secondary",
        "in_progress": "bg-primary",
        "awaiting_extra": "bg-warning text-dark",
        "completed": "bg-success",
        "cancelled": "bg-danger",
    }
    PRIORITY_BADGES = {"normal": "bg-secondary", "high": "bg-warning text-dark", "urgent": "bg-danger"}

    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="jobs")
    vehicle = models.ForeignKey("customers.Vehicle", on_delete=models.PROTECT, related_name="jobs")
    assigned_worker = models.ForeignKey(
        "workforce.WorkerProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_jobs"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_jobs"
    )
    services = models.ManyToManyField("catalog.Service", through="JobService", related_name="jobs")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    need_alert = models.BooleanField(default=False, help_text="True while extra services are still pending")
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True, help_text="Staff only - customers never see this")

    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    estimated_duration = models.PositiveIntegerField(default=0, help_text="Minutes")
    actual_duration = models.PositiveIntegerField(null=True, blank=True, help_text="Minutes")

    queue_date = models.DateField(default=timezone.localdate)
    queue_number = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["queue_date", "queue_number"], name="unique_queue_number_per_day")
        ]

    def __str__(self):
        return f"Job #{self.pk} - {self.vehicle.plate_number}"

    # ---- status helpers
    @property
    def status_badge(self):
        return self.BADGES.get(self.status, "bg-secondary")

    @property
    def priority_badge(self):
        return self.PRIORITY_BADGES.get(self.priority, "bg-secondary")

    @property
    def is_open(self):
        return self.status not in (self.Status.COMPLETED, self.Status.CANCELLED)

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, [])

    # ---- service helpers
    def pending_services(self):
        return self.job_services.filter(is_completed=False)

    def has_pending_services(self) -> bool:
        return self.pending_services().exists()

    def has_pending_extra_services(self) -> bool:
        return self.pending_services().filter(service__category__in=["detailing", "additional"]).exists()

    # ---- money (derived from the payments ledger, never stored twice)
    @property
    def amount_paid(self) -> Decimal:
        if hasattr(self, "paid_total"):  # set by selectors.with_payment_totals() to avoid N+1 queries
            return self.paid_total or Decimal("0.00")
        return self.payments.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    @property
    def balance_due(self) -> Decimal:
        return max(self.total_price - self.amount_paid, Decimal("0.00"))

    @property
    def payment_status(self) -> str:
        paid = self.amount_paid
        if paid <= 0 and self.payments.filter(amount__lt=0).exists():
            return "refunded"
        if paid >= self.total_price and (paid > 0 or self.total_price == 0):
            return "paid"
        return "partial" if paid > 0 else "pending"

    @property
    def payment_badge(self):
        return {"paid": "bg-success", "partial": "bg-warning text-dark", "refunded": "bg-info"}.get(
            self.payment_status, "bg-secondary"
        )

    @property
    def is_fully_paid(self) -> bool:
        return self.payment_status == "paid"


class JobService(TimeStampedModel):
    """One line on the job: a service, its price *at the time it was added*, and its progress."""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="job_services")
    service = models.ForeignKey("catalog.Service", on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot so later price changes don't rewrite history
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to="job_photos/%Y/%m/", blank=True)

    class Meta:
        ordering = ["service__category", "id"]
        constraints = [models.UniqueConstraint(fields=["job", "service"], name="one_line_per_service_per_job")]

    def __str__(self):
        return f"{self.service} on job #{self.job_id}"


class JobEvent(models.Model):
    """The job timeline: an append-only log of everything that happened."""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=30)
    description = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.job_id}: {self.description}"
