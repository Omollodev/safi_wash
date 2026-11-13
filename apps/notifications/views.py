from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import selectors, services
from .models import Notification


@login_required
def notification_list(request):
    qs = Notification.objects.filter(recipient=request.user).select_related("job")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "notifications/notification_list.html", {"page": page})


@login_required
@require_POST
def mark_read(request, pk):
    # Filtering on recipient means you can only touch YOUR notifications.
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    if notification.job_id:
        return redirect(_job_url(request.user, notification.job_id))
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    services.mark_all_read(request.user)
    return redirect("notifications:list")


def _job_url(user, job_id):
    """Where a notification should take this user: customers have their own job page."""
    if not job_id:
        return reverse("notifications:list")
    return reverse("portal:job_detail" if user.is_customer else "jobs:detail", args=[job_id])


@login_required
def api_notifications(request):
    """Polled by static/js/toast.js: the unread count plus the most recent notifications."""
    items = [
        {
            "id": n.pk, "title": n.title, "message": n.message, "type": n.type, "icon": n.icon,
            "is_read": n.is_read, "job_id": n.job_id, "created": n.created_at.isoformat(),
            "url": _job_url(request.user, n.job_id),
        }
        for n in selectors.recent(request.user)
    ]
    return JsonResponse({"unread": selectors.unread_count(request.user), "results": items})
