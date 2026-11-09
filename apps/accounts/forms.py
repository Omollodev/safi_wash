from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from apps.core.forms import BootstrapFormMixin, BootstrapModelForm

User = get_user_model()


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Lets browsers and password managers fill the form correctly.
        self.fields["username"].widget.attrs.update(autocomplete="username", autocapitalize="none", spellcheck="false")
        self.fields["password"].widget.attrs.update(autocomplete="current-password")


class PasswordChangeBootstrapForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class ProfileForm(BootstrapModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]


class StaffUserCreateForm(BootstrapFormMixin, UserCreationForm):
    """Used by admins/managers to create staff, workers or customers."""

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "role"]


class StaffUserEditForm(BootstrapModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role", "is_active"]


class CustomerSignupForm(BootstrapFormMixin, UserCreationForm):
    """Public sign-up. Role is forced to 'customer' in the service, never taken from the form."""

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone"]

    AUTOCOMPLETE = {
        "username": "username", "first_name": "given-name", "last_name": "family-name",
        "email": "email", "phone": "tel", "password1": "new-password", "password2": "new-password",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, value in self.AUTOCOMPLETE.items():
            if name in self.fields:
                self.fields[name].widget.attrs["autocomplete"] = value
        self.fields["username"].widget.attrs.update(autocapitalize="none", spellcheck="false")
        self.fields["phone"].widget.attrs["inputmode"] = "tel"

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
