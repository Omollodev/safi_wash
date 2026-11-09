from .models import Notification


def unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).count()


def recent(user, limit=10):
    return Notification.objects.filter(recipient=user).select_related("job")[:limit]
