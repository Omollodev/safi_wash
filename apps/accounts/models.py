from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """One login model for everybody; the `role` field decides what they can do."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        WORKER = "worker", "Worker"
        CUSTOMER = "customer", "Customer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_staff_role(self):
        return self.role in (self.Role.ADMIN, self.Role.MANAGER)

    @property
    def is_worker(self):
        return self.role == self.Role.WORKER

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    def save(self, *args, **kwargs):
        # Admin role == Django superuser/staff, so the /admin/ site works for them.
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)
