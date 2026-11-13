from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum

from apps.core.models import TimeStampedModel
from apps.jobs.models import Job


class Customer(TimeStampedModel):
    """Someone who brings a vehicle in. May or may not have a portal login (`user`)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer",
    )
    name = models.CharField(max_length=120)
    business_name = models.CharField(max_length=120, blank=True, help_text="For fleet/company customers")
    phone = models.CharField(max_length=20)
    phone_secondary = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    service_preferences = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_vip = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    # Loyalty numbers are *calculated* from jobs, never stored, so they cannot go out of sync.
    @property
    def total_visits(self):
        return self.jobs.filter(status=Job.Status.COMPLETED).count()

    @property
    def total_spent(self):
        return self.jobs.filter(status=Job.Status.COMPLETED).aggregate(t=Sum("total_price"))["t"] or 0


class Vehicle(TimeStampedModel):
    class VehicleType(models.TextChoices):
        SEDAN = "sedan", "Sedan"
        HATCHBACK = "hatchback", "Hatchback"
        SUV = "suv", "SUV"
        PICKUP = "pickup", "Pickup / Truck"
        VAN = "van", "Van / Minibus"
        SPORTS = "sports_car", "Sports car"
        LUXURY = "luxury_car", "Luxury car"
        ELECTRIC = "electric_car", "Electric car"
        MOTORCYCLE = "motorcycle", "Motorcycle"
        OTHER = "other", "Other"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="vehicles")
    plate_number = models.CharField(max_length=20, unique=True)
    make = models.CharField(max_length=60)
    model = models.CharField(max_length=60)
    year = models.PositiveIntegerField(null=True, blank=True)
    color = models.CharField(max_length=40, blank=True)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, default=VehicleType.SEDAN)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plate_number"]

    def __str__(self):
        return f"{self.plate_number} - {self.make} {self.model}"

    def clean(self):
        if self.plate_number:
            self.plate_number = self.plate_number.upper().replace(" ", "")
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def description(self):
        parts = [str(self.year) if self.year else "", self.color, self.make, self.model]
        return " ".join(p for p in parts if p)
