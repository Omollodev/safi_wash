"""Read-only queries for jobs."""
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.templatetags.money import money

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


def board_payload():
    """
    Active jobs grouped by status, with everything a board card shows.
    One function feeds both the live JSON API and the first page render, so they can never disagree.
    """
    board = {"waiting": [], "in_progress": [], "awaiting_extra": []}
    jobs = active_jobs().prefetch_related("job_services__service")
    for job in jobs:
        names = [line.service.name for line in job.job_services.all()]
        summary = names[0] + (f" +{len(names) - 1}" if len(names) > 1 else "") if names else ""
        board[job.status].append({
            "id": job.pk, "queue": job.queue_number, "plate": job.vehicle.plate_number,
            "customer": job.customer.name, "priority": job.priority, "need_alert": job.need_alert,
            "worker": job.assigned_worker.name if job.assigned_worker else None,
            "status": job.status, "status_display": job.get_status_display(),
            "priority_display": job.get_priority_display(),
            "services": names, "service_summary": summary,
            "created_at": timezone.localtime(job.created_at).isoformat(),
            "started_at": timezone.localtime(job.started_at).isoformat() if job.started_at else None,
            "total": str(job.total_price), "total_display": money(job.total_price),
        })
    return board
