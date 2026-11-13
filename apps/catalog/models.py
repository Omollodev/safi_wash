from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Service(TimeStampedModel):
    """Something the car wash sells: 'Full exterior wash', 'Engine bay clean', ..."""

    class Category(models.TextChoices):
        EXTERIOR = "exterior", "Exterior"
        INTERIOR = "interior", "Interior"
        DETAILING = "detailing", "Detailing"
        ADDITIONAL = "additional", "Additional services"

  
    BASIC_CATEGORIES = (Category.EXTERIOR, Category.INTERIOR)
    BASIC_CATEGORIES = (Category.EXTERIOR, Category.INTERIOR)
    EXTRA_CATEGORIES = (Category.DETAILING, Category.ADDITIONAL)

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.EXTERIOR)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    estimated_duration = models.PositiveIntegerField(default=30, help_text="Minutes")
    requires_special_equipment = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "display_order", "name"]

    def __str__(self):
        return self.name

    @property
    def is_extra(self):
        return self.category in self.EXTRA_CATEGORIES


def _max_photo_size(file):
    if file.size > 5 * 1024 * 1024:
        raise ValidationError("Photo must be smaller than 5 MB.")


class GalleryPhoto(TimeStampedModel):
    """A photo shown in the public gallery on the landing page (managed in the admin)."""

    title = models.CharField(max_length=80)
    alt_text = models.CharField(
        max_length=160, blank=True, help_text="Describe the photo for screen readers. Defaults to the title."
    )
    image = models.ImageField(upload_to="gallery/%Y/%m/", validators=[_max_photo_size])
    is_featured = models.BooleanField(default=False, help_text="Use as the big hero photo (the newest featured one wins)")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def alt(self):
        return self.alt_text or self.title
