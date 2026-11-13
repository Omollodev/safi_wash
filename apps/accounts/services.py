"""Business logic for accounts (kept out of views so it is easy to test)."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse

from .tokens import make_verification_token, read_verification_token

User = get_user_model()


def send_verification_email(request, user) -> None:
    token = make_verification_token(user)
    url = request.build_absolute_uri(reverse("accounts:verify_email", args=[token]))
    send_mail(
        subject=f"Verify your {settings.BUSINESS['name']} account",
        message=(
            f"Hi {user.first_name or user.username},\n\n"
            f"Please confirm your email by opening this link (valid for 24 hours):\n{url}\n\n"
            "If you did not sign up, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def verify_email(token: str):
    """Activate the user the token belongs to. Returns the user or None."""
    payload = read_verification_token(token)
    if not payload:
        return None
    user = User.objects.filter(pk=payload["uid"]).first()
    if user is None:
        return None
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    return user
