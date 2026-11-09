from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class WorkerProfile(TimeStampedModel):
    """Extra data for users whose role is 'worker'."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="worker_profile")
    employee_id = models.CharField(max_length=20, blank=True)
    skills = models.ManyToManyField("catalog.Service", blank=True, related_name="skilled_workers")
    is_available = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))
    total_ratings = models.PositiveIntegerField(default=0)
    hired_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["user__first_name", "user__username"]

    def __str__(self):
        return str(self.user)

    @property
    def name(self):
        return str(self.user)

    def can_perform(self, service) -> bool:
        """A worker with no listed skills is treated as a generalist."""
        return not self.skills.exists() or self.skills.filter(pk=service.pk).exists()
