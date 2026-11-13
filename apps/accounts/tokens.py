"""Email-verification links using Django's signed tokens (no extra table needed)."""
from django.conf import settings
from django.core import signing

_SALT = "accounts.email-verification"


def make_verification_token(user) -> str:
    return signing.dumps({"uid": user.pk}, salt=_SALT)


def read_verification_token(token: str):
    """Return the payload dict, or None if the token is invalid/expired."""
    try:
        return signing.loads(token, salt=_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    except signing.BadSignature:  # includes SignatureExpired
        return None
