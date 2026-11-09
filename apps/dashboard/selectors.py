"""Numbers for the dashboard and reports -- all aggregated in the database."""
from datetime import timedelta
from itertools import groupby

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.catalog.models import GalleryPhoto, Service
from apps.customers.models import Customer
from apps.jobs.models import Job, JobService
from apps.payments.models import Payment
from apps.workforce.models import WorkerProfile


def _period_start(days: int):
    return timezone.localdate() - timedelta(days=days)


def overview():
    today = timezone.localdate()
    counts = dict(Job.objects.filter(status__in=["waiting", "in_progress", "awaiting_extra"])
                  .values_list("status").annotate(n=Count("id")).order_by())
    return {
        "waiting": counts.get("waiting", 0),
        "in_progress": counts.get("in_progress", 0),
        "awaiting_extra": counts.get("awaiting_extra", 0),
        "completed_today": Job.objects.filter(status="completed", completed_at__date=today).count(),
        "collected_today": Payment.objects.filter(created_at__date=today).aggregate(t=Sum("amount"))["t"] or 0,
        "alerts": Job.objects.filter(need_alert=True, status__in=["in_progress", "awaiting_extra"]).count(),
        "workers_available": WorkerProfile.objects.filter(is_available=True, user__is_active=True).count(),
        "workers_total": WorkerProfile.objects.filter(user__is_active=True).count(),
    }


def period_report(days: int):
    """days=0 -> today, 6 -> last 7 days, 29 -> last 30 days."""
    start = _period_start(days)
    done = Job.objects.filter(status="completed", completed_at__date__gte=start)
    return {
        "jobs": done.count(),
        "billed": done.aggregate(t=Sum("total_price"))["t"] or 0,
        "collected": Payment.objects.filter(created_at__date__gte=start).aggregate(t=Sum("amount"))["t"] or 0,
        "avg_minutes": round(done.aggregate(a=Avg("actual_duration"))["a"] or 0),
    }


def top_workers(days: int = 29, limit: int = 5):
    start = _period_start(days)
    return (
        WorkerProfile.objects.select_related("user")
        .annotate(done=Count("assigned_jobs", filter=Q(assigned_jobs__status="completed", assigned_jobs__completed_at__date__gte=start)))
        .filter(done__gt=0)
        .order_by("-done")[:limit]
    )


def popular_services(days: int = 29, limit: int = 8):
    start = _period_start(days)
    return (
        JobService.objects.filter(job__created_at__date__gte=start)
        .values("service__name")
        .annotate(times=Count("id"), revenue=Sum("price"))
        .order_by("-times")[:limit]
    )


def payment_methods(days: int = 29):
    start = _period_start(days)
    return (
        Payment.objects.filter(created_at__date__gte=start, amount__gt=0)
        .values("method").annotate(total=Sum("amount"), n=Count("id")).order_by("-total")
    )


# ---------------------------------------------------------------- public landing page
CATEGORY_ICONS = {  # Bootstrap Icons shown on the landing page tabs and cards
    "exterior": "bi-droplet-half",
    "interior": "bi-wind",
    "detailing": "bi-stars",
    "additional": "bi-plus-circle",
}


def landing_services():
    """Active services grouped by category, in the order the categories are defined."""
    order = [value for value, _ in Service.Category.choices]
    services = sorted(Service.objects.filter(is_active=True), key=lambda s: (order.index(s.category), s.display_order, s.name))
    labels = dict(Service.Category.choices)
    return [
        {"key": key, "label": labels[key], "icon": CATEGORY_ICONS.get(key, "bi-droplet"), "services": list(items)}
        for key, items in groupby(services, key=lambda s: s.category)
    ]


def landing_photos():
    photos = list(GalleryPhoto.objects.filter(is_active=True))
    featured = sorted((p for p in photos if p.is_featured), key=lambda p: p.created_at, reverse=True)
    return {"hero": featured[0] if featured else None, "gallery": photos}


def landing_stats():
    """Only REAL numbers from the database. Zero values are dropped, so a new shop shows nothing fake."""
    stats = [
        ("Car washed", "Cars washed", Job.objects.filter(status="completed").count()),
        ("Happy customer", "Happy customers", Customer.objects.filter(is_active=True).count()),
        ("Service on offer", "Services on offer", Service.objects.filter(is_active=True).count()),
        ("Team member", "Team members", WorkerProfile.objects.filter(user__is_active=True).count()),
    ]
    return [{"label": one if value == 1 else many, "value": value} for one, many, value in stats if value > 0]
