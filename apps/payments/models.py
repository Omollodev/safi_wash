from django.conf import settings
from django.db import models


class Payment(models.Model):
    """
    The money ledger. One row per payment (positive) or refund (negative).
    A job's paid amount is simply the SUM of its rows -- so it can never drift out of sync.
    """

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"

    job = models.ForeignKey("jobs.Job", on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Negative = refund")
    method = models.CharField(max_length=10, choices=Method.choices)
    reference = models.CharField(max_length=64, blank=True, null=True, help_text="M-Pesa receipt number")
    phone = models.CharField(max_length=20, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # An M-Pesa receipt can only ever be counted once (blocks replayed callbacks).
            # Use nullable field with unique=True; MySQL allows multiple NULLs.
            models.UniqueConstraint(fields=["reference"], name="unique_payment_reference")
        ]

    def save(self, *args, **kwargs):
        # Convert empty string to None for unique constraint compatibility (MySQL allows multiple NULLs)
        if self.reference == "":
            self.reference = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_method_display()} {self.amount} on job #{self.job_id}"

    @property
    def is_refund(self):
        return self.amount < 0


class MpesaRequest(models.Model):
    """One STK Push prompt sent to a customer's phone, and what happened to it."""

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for customer"
        SUCCESS = "success", "Paid"
        FAILED = "failed", "Failed"

    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="mpesa_requests")
    checkout_request_id = models.CharField(max_length=120, unique=True)
    merchant_request_id = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result_desc = models.CharField(max_length=255, blank=True)
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="mpesa_request")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"STK {self.checkout_request_id} ({self.status})"
