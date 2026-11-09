"""
Everything that CHANGES a job lives here.

Views call these functions; views never edit job fields directly. That gives us
one place to enforce the rules (and one place to unit-test them).
Rule violations raise JobError with a human-readable message.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_managers

from .models import Job, JobEvent, JobService


class JobError(Exception):
    """A business-rule problem the user should be told about."""


# ---------------------------------------------------------------- helpers
def log_event(job, kind, description, user=None, notes=""):
    return JobEvent.objects.create(job=job, kind=kind, description=description, user=user, notes=notes)


def recalculate_totals(job: Job) -> None:
    lines = job.job_services.select_related("service")
    job.estimated_price = sum((line.price for line in lines), Decimal("0.00"))
    job.estimated_duration = sum(line.service.estimated_duration for line in lines)
    job.total_price = max(job.estimated_price - job.discount, Decimal("0.00"))
    job.need_alert = job.has_pending_extra_services()
    job.save(update_fields=["estimated_price", "estimated_duration", "total_price", "need_alert", "updated_at"])


def can_update_services(user, job: Job) -> bool:
    """Admins/managers, or the worker assigned to this job. Customers never."""
    if user.is_staff_role:
        return True
    profile = getattr(user, "worker_profile", None) if user.is_worker else None
    return bool(profile and job.assigned_worker_id == profile.pk)


# ---------------------------------------------------------------- create
@transaction.atomic
def create_job(*, customer, vehicle, services, created_by=None, priority=Job.Priority.NORMAL,
               special_instructions="", discount=Decimal("0.00"), assigned_worker=None) -> Job:
    if vehicle.customer_id != customer.pk:
        raise JobError("That vehicle does not belong to this customer.")
    if not services:
        raise JobError("Choose at least one service.")

    today = timezone.localdate()
    last = Job.objects.filter(queue_date=today).aggregate(m=Max("queue_number"))["m"] or 0
    job = Job.objects.create(
        customer=customer, vehicle=vehicle, created_by=created_by, priority=priority,
        special_instructions=special_instructions, discount=discount,
        assigned_worker=assigned_worker, queue_date=today, queue_number=last + 1,
    )
    for service in services:
        JobService.objects.create(job=job, service=service, price=service.price)
    recalculate_totals(job)
    log_event(job, "created", f"Job created (queue #{job.queue_number})", created_by)

    if assigned_worker:
        _notify_worker_assigned(job, assigned_worker)
    return job


# ---------------------------------------------------------------- status
@transaction.atomic
def change_status(job: Job, new_status: str, user=None, notes: str = "") -> Job:
    if not job.can_transition_to(new_status):
        raise JobError(f"A {job.get_status_display().lower()} job cannot move to '{new_status}'.")

    if new_status == Job.Status.COMPLETED and job.has_pending_services():
        count = job.pending_services().count()
        raise JobError(f"{count} service(s) still pending. Mark every service as done first.")

    old_status = job.status
    job.status = new_status
    now = timezone.now()
    if new_status == Job.Status.IN_PROGRESS and not job.started_at:
        job.started_at = now
    if new_status == Job.Status.COMPLETED:
        job.completed_at = now
        if job.started_at:
            job.actual_duration = int((now - job.started_at).total_seconds() // 60)
    job.need_alert = job.has_pending_extra_services()
    job.save()

    log_event(job, "status_change", f"Status changed from {old_status} to {new_status}", user, notes)

    if new_status == Job.Status.COMPLETED:
        _notify_completed(job, user)
    return job


def cancel_job(job: Job, user=None, reason: str = "") -> Job:
    return change_status(job, Job.Status.CANCELLED, user, reason)


# ---------------------------------------------------------------- worker
@transaction.atomic
def assign_worker(job: Job, worker, user=None) -> Job:
    if not job.is_open:
        raise JobError("You cannot assign a worker to a finished job.")
    job.assigned_worker = worker
    job.save(update_fields=["assigned_worker", "updated_at"])
    log_event(job, "worker_assigned", f"Worker assigned: {worker.name}", user)
    _notify_worker_assigned(job, worker)
    return job


# ---------------------------------------------------------------- services on a job
@transaction.atomic
def add_service(job: Job, service, user=None, notes: str = "", price=None) -> JobService:
    if not job.is_open:
        raise JobError("You cannot add services to a finished job.")
    if job.job_services.filter(service=service).exists():
        raise JobError(f'"{service.name}" is already on this job.')

    line = JobService.objects.create(
        job=job, service=service, notes=notes, price=service.price if price is None else price
    )
    # Adding work while the job is running pauses it until the extra is approved/done.
    if job.status == Job.Status.IN_PROGRESS:
        job.status = Job.Status.AWAITING_EXTRA
        job.save(update_fields=["status", "updated_at"])
    recalculate_totals(job)
    log_event(job, "extra_service_added", f"Extra service added: {service.name}", user, notes)

    if job.assigned_worker:
        notify(
            job.assigned_worker.user, Notification.Type.EXTRA_SERVICE, "Extra service added",
            f'Extra service "{service.name}" added to Job #{job.pk}', job=job,
        )
    return line


@transaction.atomic
def complete_service(line: JobService, user=None, notes: str = "", photo=None) -> JobService:
    job = line.job
    if not job.is_open:
        raise JobError("This job is already finished.")
    if not can_update_services(user, job):
        raise JobError("You cannot update services on this job.")
    line.is_completed = True
    line.completed_at = timezone.now()
    line.completed_by = user
    if notes:
        line.notes = notes
    if photo:
        line.photo = photo
    line.save()

    job.need_alert = job.has_pending_extra_services()
    job.save(update_fields=["need_alert", "updated_at"])
    log_event(job, "service_completed", f'Service "{line.service.name}" marked as completed', user)

    if not job.has_pending_services() and job.customer.user_id:
        notify(
            job.customer.user, Notification.Type.JOB_UPDATED, "All services done",
            f"All services on your job #{job.pk} ({job.vehicle.plate_number}) are done.", job=job,
        )
    return line


@transaction.atomic
def uncomplete_service(line: JobService, user=None) -> JobService:
    job = line.job
    if not job.is_open:
        raise JobError("This job is already finished.")
    if not can_update_services(user, job):
        raise JobError("You cannot update services on this job.")
    line.is_completed = False
    line.completed_at = None
    line.completed_by = None
    line.save()
    job.need_alert = job.has_pending_extra_services()
    job.save(update_fields=["need_alert", "updated_at"])
    log_event(job, "service_reopened", f'Service "{line.service.name}" marked as not done', user)
    return line


@transaction.atomic
def update_job_details(job: Job, *, priority, special_instructions, internal_notes, discount, user=None) -> Job:
    if not job.is_open:
        raise JobError("Finished jobs cannot be edited.")
    job.priority = priority
    job.special_instructions = special_instructions
    job.internal_notes = internal_notes
    job.discount = discount
    job.save()
    recalculate_totals(job)
    log_event(job, "edited", "Job details updated", user)
    return job


# ---------------------------------------------------------------- notifications
def _notify_worker_assigned(job, worker):
    notify(
        worker.user, Notification.Type.JOB_ASSIGNED, "Job assigned",
        f"You have been assigned to Job #{job.pk} - {job.vehicle.plate_number}", job=job,
    )


def _notify_completed(job, completed_by):
    notify_managers(
        Notification.Type.JOB_COMPLETED, "Job completed",
        f"Job #{job.pk} ({job.vehicle.plate_number}) is complete.", job=job, exclude=completed_by,
    )
    if job.customer.user_id:
        notify(
            job.customer.user, Notification.Type.JOB_COMPLETED, "Your car is ready",
            f"Your {job.vehicle.make} {job.vehicle.model} ({job.vehicle.plate_number}) is ready for pickup. "
            f"Balance due: {job.balance_due}.",
            job=job, sms=True,
        )
