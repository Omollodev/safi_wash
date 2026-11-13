from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import WorkerProfile


def available_workers():
    return WorkerProfile.objects.filter(is_available=True, user__is_active=True).exclude(
        assigned_jobs__status="in_progress"
    )


def jobs_completed_today(worker) -> int:
    return worker.assigned_jobs.filter(status="completed", completed_at__date=timezone.localdate()).count()


def is_busy(worker) -> bool:
    return worker.assigned_jobs.filter(status__in=["in_progress", "awaiting_extra"]).exists()


def workers_with_stats():
    """All workers + completed job count + average minutes per job, in ONE query."""
    return WorkerProfile.objects.select_related("user").annotate(
        completed_count=Count("assigned_jobs", filter=Q(assigned_jobs__status="completed")),
        avg_minutes=Avg("assigned_jobs__actual_duration", filter=Q(assigned_jobs__status="completed")),
    )
