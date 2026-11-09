from django.conf import settings


def site(request):
    """Variables available in every template: {{ BUSINESS.name }}, {{ unread_count }}."""
    unread = 0
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from apps.notifications.selectors import unread_count

        unread = unread_count(user)
    return {"BUSINESS": settings.BUSINESS, "unread_count": unread}
