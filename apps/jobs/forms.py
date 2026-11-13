from django import forms

from apps.catalog.models import Service
from apps.core.forms import BootstrapForm, BootstrapModelForm
from apps.customers.models import Vehicle
from apps.workforce.models import WorkerProfile

from .models import Job

MAX_PHOTO_BYTES = 5 * 1024 * 1024


class JobCreateForm(BootstrapForm):
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none(), help_text="The customer comes from the vehicle.")
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(is_active=True), widget=forms.CheckboxSelectMultiple
    )
    priority = forms.ChoiceField(choices=Job.Priority.choices, initial=Job.Priority.NORMAL)
    discount = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2, initial=0, required=False)
    special_instructions = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    assigned_worker = forms.ModelChoiceField(queryset=WorkerProfile.objects.none(), required=False)
    auto_assign = forms.BooleanField(required=False, label="Auto-assign the best available worker")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = Vehicle.objects.filter(is_active=True, customer__is_active=True).select_related("customer")
        self.fields["assigned_worker"].queryset = WorkerProfile.objects.filter(user__is_active=True).select_related("user")
        self.fields["services"].widget.attrs["class"] = ""

    def clean_discount(self):
        return self.cleaned_data.get("discount") or 0


class JobEditForm(BootstrapModelForm):
    class Meta:
        model = Job
        fields = ["priority", "special_instructions", "internal_notes", "discount"]
        widgets = {
            "special_instructions": forms.Textarea(attrs={"rows": 2}),
            "internal_notes": forms.Textarea(attrs={"rows": 2}),
        }


class StatusForm(BootstrapForm):
    status = forms.ChoiceField(choices=Job.Status.choices)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class AssignWorkerForm(BootstrapForm):
    worker = forms.ModelChoiceField(queryset=WorkerProfile.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["worker"].queryset = WorkerProfile.objects.filter(user__is_active=True).select_related("user")


class AddServiceForm(BootstrapForm):
    service = forms.ModelChoiceField(queryset=Service.objects.filter(is_active=True))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    price = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2,
                               help_text="Leave empty to use the catalogue price")


class CompleteServiceForm(BootstrapForm):
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    photo = forms.ImageField(required=False)

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and photo.size > MAX_PHOTO_BYTES:
            raise forms.ValidationError("Photo must be smaller than 5 MB.")
        return photo
