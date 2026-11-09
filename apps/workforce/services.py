from decimal import Decimal

from django.utils import timezone

from .models import WorkerProfile


def ensure_worker_profile(user) -> WorkerProfile:
    profile, _ = WorkerProfile.objects.get_or_create(
        user=user, defaults={"employee_id": f"W{user.pk:04d}", "hired_date": timezone.localdate()}
    )
    return profile


def add_rating(worker: WorkerProfile, value) -> None:
    """Fold a new 0-5 rating into the running average."""
    value = Decimal(str(value))
    if not Decimal("0") <= value <= Decimal("5"):
        raise ValueError("Rating must be between 0 and 5")
    total = worker.rating * worker.total_ratings + value
    worker.total_ratings += 1
    worker.rating = (total / worker.total_ratings).quantize(Decimal("0.01"))
    worker.save(update_fields=["rating", "total_ratings"])


def pick_best_available_worker(service=None):
    """
    Auto-assignment rule (same as the old system):
      1. must be available and active
      2. must have the skill (if a service is given)
      3. higher rating first, then fewer jobs completed today
    """
    from apps.workforce.selectors import available_workers, jobs_completed_today

    workers = available_workers()
    if service is not None:
        workers = workers.filter(skills=service) or workers
    return sorted(workers, key=lambda w: (-w.rating, jobs_completed_today(w)))[0] if workers else None
