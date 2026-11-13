"""The ONE place the rest of the project calls to tell someone something."""
from django.contrib.auth import get_user_model

from .models import Notification
from .sms import send_sms

User = get_user_model()


def notify(recipient, type, title, message, job=None, sms=False) -> Notification:
    notification = Notification.objects.create(
        recipient=recipient, type=type, title=title, message=message, job=job
    )
    if sms and recipient.phone:
        send_sms(recipient.phone, f"{title}: {message}")
    return notification


def notify_managers(type, title, message, job=None, exclude=None) -> None:
    managers = User.objects.filter(role__in=["admin", "manager"], is_active=True)
    if exclude is not None:
        managers = managers.exclude(pk=exclude.pk)
    for manager in managers:
        notify(manager, type, title, message, job=job)


def mark_all_read(user) -> int:
    from django.utils import timezone

    return Notification.objects.filter(recipient=user, is_read=False).update(is_read=True, read_at=timezone.now())
