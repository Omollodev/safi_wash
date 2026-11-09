from django import forms
from django.contrib.auth import get_user_model

from apps.catalog.models import Service
from apps.core.forms import BootstrapFormMixin, BootstrapModelForm

from .models import WorkerProfile

User = get_user_model()


class WorkerForm(BootstrapModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=20, required=False)
    skills = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = WorkerProfile
        fields = ["employee_id", "hired_date", "skills", "is_available", "notes"]
        widgets = {"hired_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Checkbox lists should not get the form-select class
        self.fields["skills"].widget.attrs["class"] = ""
        if self.instance.pk:
            u = self.instance.user
            self.fields["first_name"].initial = u.first_name
            self.fields["last_name"].initial = u.last_name
            self.fields["phone"].initial = u.phone

    def save(self, commit=True):
        profile = super().save(commit=commit)
        u = profile.user
        u.first_name = self.cleaned_data["first_name"]
        u.last_name = self.cleaned_data["last_name"]
        u.phone = self.cleaned_data["phone"]
        u.save(update_fields=["first_name", "last_name", "phone"])
        return profile
