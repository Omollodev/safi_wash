from django import forms

from apps.core.forms import BootstrapModelForm

from .models import Service


class ServiceForm(BootstrapModelForm):
    class Meta:
        model = Service
        fields = [
            "name", "description", "category", "price", "estimated_duration",
            "requires_special_equipment", "display_order", "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
