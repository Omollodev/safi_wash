from django import forms

from apps.core.forms import BootstrapForm, BootstrapModelForm

from .models import Customer, Vehicle


class CustomerForm(BootstrapModelForm):
    class Meta:
        model = Customer
        fields = [
            "name", "business_name", "phone", "phone_secondary", "email", "address",
            "service_preferences", "notes", "is_vip", "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "service_preferences": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class VehicleForm(BootstrapModelForm):
    class Meta:
        model = Vehicle
        fields = ["plate_number", "make", "model", "year", "color", "vehicle_type", "mileage", "notes", "is_active"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean_plate_number(self):
        plate = self.cleaned_data["plate_number"].upper().replace(" ", "")
        clash = Vehicle.objects.filter(plate_number=plate).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("A vehicle with this plate already exists.")
        return plate


class PortalVehicleForm(VehicleForm):
    """Customers adding their own car cannot toggle the active flag."""

    class Meta(VehicleForm.Meta):
        fields = ["plate_number", "make", "model", "year", "color", "vehicle_type", "mileage", "notes"]


class QuickAddForm(BootstrapForm):
    """Customer + vehicle in one go (walk-in at the counter)."""

    name = forms.CharField(max_length=120)
    phone = forms.CharField(max_length=20)
    email = forms.EmailField(required=False)
    plate_number = forms.CharField(max_length=20)
    make = forms.CharField(max_length=60)
    model = forms.CharField(max_length=60)
    color = forms.CharField(max_length=40, required=False)
    vehicle_type = forms.ChoiceField(choices=Vehicle.VehicleType.choices, initial="sedan")

    def clean_plate_number(self):
        plate = self.cleaned_data["plate_number"].upper().replace(" ", "")
        if Vehicle.objects.filter(plate_number=plate).exists():
            raise forms.ValidationError("A vehicle with this plate already exists.")
        return plate

    def split(self):
        d = self.cleaned_data
        customer = {k: d[k] for k in ("name", "phone", "email")}
        vehicle = {k: d[k] for k in ("plate_number", "make", "model", "color", "vehicle_type")}
        return customer, vehicle
