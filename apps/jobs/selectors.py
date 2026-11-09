"""Read-only queries for jobs."""
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Job

ACTIVE_STATUSES = ["waiting", "in_progress", "awaiting_extra"]


def base_queryset():
    """Jobs with everything a list/card needs, fetched in as few queries as possible."""
    return Job.objects.select_related("customer", "vehicle", "assigned_worker__user").annotate(
        paid_total=Coalesce(Sum("payments__amount"), Value(0), output_field=DecimalField())
    )


def filter_jobs(qs, status="", priority="", q=""):
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if q:
        qs = qs.filter(
            Q(vehicle__plate_number__icontains=q) | Q(customer__name__icontains=q) | Q(customer__phone__icontains=q)
        )
    return qs


def status_counts():
    counts = {s: 0 for s in Job.Status.values}
    for row in Job.objects.values("status").order_by().annotate(n=Count("id")):
        counts[row["status"]] = row["n"]
    return counts


def active_jobs():
    return base_queryset().filter(status__in=ACTIVE_STATUSES).order_by("queue_date", "queue_number")


def jobs_needing_alert():
    return base_queryset().filter(need_alert=True, status__in=ACTIVE_STATUSES)


def todays_jobs():
    return base_queryset().filter(created_at__date=timezone.localdate())


def jobs_for_customer(customer):
    return base_queryset().filter(customer=customer)
