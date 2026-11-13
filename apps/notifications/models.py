from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class Type(models.TextChoices):
        JOB_ASSIGNED = "job_assigned", "Job assigned"
        JOB_UPDATED = "job_updated", "Job updated"
        JOB_COMPLETED = "job_completed", "Job completed"
        EXTRA_SERVICE = "extra_service", "Extra service added"
        PAYMENT = "payment", "Payment"
        ALERT = "alert", "Alert"
        INFO = "info", "Information"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.INFO)
    title = models.CharField(max_length=140)
    message = models.TextField()
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.title} -> {self.recipient}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    @property
    def icon(self):
        return {
            "job_assigned": "user-check",
            "job_updated": "refresh-cw",
            "job_completed": "circle-check",
            "extra_service": "circle-plus",
            "payment": "wallet",
            "alert": "triangle-alert",
        }.get(self.type, "info")
