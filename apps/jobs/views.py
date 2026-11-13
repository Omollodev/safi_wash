"""
HTTP layer for jobs. Each view: check permission -> validate form -> call a
service -> show a message -> redirect. No business rules live here.
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permissions import staff_required, worker_or_staff_required
from apps.workforce.services import pick_best_available_worker

from . import selectors, services
from .forms import (
    AddServiceForm, AssignWorkerForm, CompleteServiceForm, JobCreateForm, JobEditForm, StatusForm,
)
from .models import Job, JobService
from .services import JobError


def _wants_json(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _respond(request, job, ok, message, extra=None):
    """Same code path for normal form posts and for the AJAX buttons on the board."""
    if _wants_json(request):
        payload = {"success": ok, "message": message, **(extra or {})}
        return JsonResponse(payload, status=200 if ok else 400)
    (messages.success if ok else messages.error)(request, message)
    return redirect("jobs:detail", pk=job.pk)


@worker_or_staff_required
def job_list(request):
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    q = request.GET.get("q", "")
    jobs = selectors.filter_jobs(selectors.base_queryset(), status, priority, q)
    page = Paginator(jobs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "jobs/job_list.html",
        {
            "page": page, "status": status, "priority": priority, "q": q,
            "counts": selectors.status_counts(), "statuses": Job.Status.choices,
            "priorities": Job.Priority.choices,
        },
    )


@worker_or_staff_required
def job_detail(request, pk):
    job = get_object_or_404(selectors.base_queryset(), pk=pk)
    return render(
        request,
        "jobs/job_detail.html",
        {
            "job": job,
            "lines": job.job_services.select_related("service", "completed_by"),
            "events": job.events.select_related("user"),
            "payments": job.payments.select_related("recorded_by"),
            "can_update_services": services.can_update_services(request.user, job),
            "status_form": StatusForm(),
            "worker_form": AssignWorkerForm(),
            "service_form": AddServiceForm(),
            "complete_form": CompleteServiceForm(),
            "next_statuses": [(s, dict(Job.Status.choices)[s]) for s in Job.ALLOWED_TRANSITIONS[job.status]],
        },
    )


@staff_required
def job_create(request):
    initial = {"vehicle": request.GET.get("vehicle")} if request.GET.get("vehicle") else None
    form = JobCreateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        worker = d["assigned_worker"]
        if d["auto_assign"] and not worker:
            worker = pick_best_available_worker(next(iter(d["services"]), None))
        try:
            job = services.create_job(
                customer=d["vehicle"].customer, vehicle=d["vehicle"], services=list(d["services"]),
                created_by=request.user, priority=d["priority"], discount=d["discount"],
                special_instructions=d["special_instructions"], assigned_worker=worker,
            )
        except JobError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Job #{job.pk} created (queue #{job.queue_number}).")
            return redirect("jobs:detail", pk=job.pk)
    return render(request, "jobs/job_form.html", {"form": form})


@staff_required
def job_edit(request, pk):
    job = get_object_or_404(Job, pk=pk)
    if not job.is_open:
        messages.warning(request, "Finished jobs cannot be edited.")
        return redirect("jobs:detail", pk=pk)
    form = JobEditForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            services.update_job_details(
                job, priority=d["priority"], special_instructions=d["special_instructions"],
                internal_notes=d["internal_notes"], discount=d["discount"], user=request.user,
            )
        except JobError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Job updated.")
            return redirect("jobs:detail", pk=pk)
    return render(request, "jobs/job_edit.html", {"form": form, "job": job})


@worker_or_staff_required
@require_POST
def job_change_status(request, pk):
    job = get_object_or_404(Job, pk=pk)
    # Workers may only move jobs that are assigned to them.
    if not services.can_update_services(request.user, job):
        return _respond(request, job, False, "You cannot change this job's status.")
    form = StatusForm(request.POST)
    if not form.is_valid():
        return _respond(request, job, False, "Invalid status.")
    try:
        services.change_status(job, form.cleaned_data["status"], request.user, form.cleaned_data["notes"])
    except JobError as exc:
        return _respond(request, job, False, str(exc))
    return _respond(request, job, True, f"Status changed to {job.get_status_display()}.",
                    {"status": job.status, "status_display": job.get_status_display(), "badge": job.status_badge})


@staff_required
@require_POST
def job_assign_worker(request, pk):
    job = get_object_or_404(Job, pk=pk)
    form = AssignWorkerForm(request.POST)
    if not form.is_valid():
        return _respond(request, job, False, "Choose a worker.")
    try:
        services.assign_worker(job, form.cleaned_data["worker"], request.user)
    except JobError as exc:
        return _respond(request, job, False, str(exc))
    return _respond(request, job, True, f"{form.cleaned_data['worker'].name} assigned.")


@staff_required
@require_POST
def job_add_service(request, pk):
    job = get_object_or_404(Job, pk=pk)
    form = AddServiceForm(request.POST)
    if not form.is_valid():
        return _respond(request, job, False, "Choose a valid service.")
    d = form.cleaned_data
    try:
        services.add_service(job, d["service"], request.user, d["notes"], d["price"])
    except JobError as exc:
        return _respond(request, job, False, str(exc))
    return _respond(request, job, True, f'"{d["service"].name}" added.')


@worker_or_staff_required
@require_POST
def service_complete(request, pk, line_pk):
    job = get_object_or_404(Job, pk=pk)
    line = get_object_or_404(JobService, pk=line_pk, job=job)
    form = CompleteServiceForm(request.POST, request.FILES)
    if not form.is_valid():
        return _respond(request, job, False, "; ".join(sum(form.errors.values(), [])))
    try:
        services.complete_service(line, request.user, form.cleaned_data["notes"], form.cleaned_data["photo"])
    except JobError as exc:
        return _respond(request, job, False, str(exc))
    return _respond(request, job, True, f'"{line.service.name}" marked as done.',
                    {"pending_count": job.pending_services().count()})


@worker_or_staff_required
@require_POST
def service_uncomplete(request, pk, line_pk):
    job = get_object_or_404(Job, pk=pk)
    line = get_object_or_404(JobService, pk=line_pk, job=job)
    try:
        services.uncomplete_service(line, request.user)
    except JobError as exc:
        return _respond(request, job, False, str(exc))
    return _respond(request, job, True, f'"{line.service.name}" re-opened.')


@staff_required
@require_POST
def job_cancel(request, pk):
    job = get_object_or_404(Job, pk=pk)
    try:
        services.cancel_job(job, request.user, request.POST.get("reason", ""))
    except JobError as exc:
        return _respond(request, job, False, str(exc))
    return _respond(request, job, True, f"Job #{job.pk} cancelled.")


@staff_required
def job_print(request, pk):
    job = get_object_or_404(selectors.base_queryset(), pk=pk)
    return render(request, "jobs/job_print.html", {"job": job, "lines": job.job_services.select_related("service")})


# ---------------------------------------------------------------- JSON API (polled by the dashboard)
@worker_or_staff_required
def api_job_detail(request, pk):
    job = get_object_or_404(selectors.base_queryset(), pk=pk)
    return JsonResponse({
        "id": job.pk, "status": job.status, "status_display": job.get_status_display(),
        "plate": job.vehicle.plate_number, "customer": job.customer.name,
        "worker": job.assigned_worker.name if job.assigned_worker else None,
        "total": str(job.total_price), "paid": str(job.amount_paid), "balance": str(job.balance_due),
        "pending_services": job.pending_services().count(), "need_alert": job.need_alert,
    })


@worker_or_staff_required
def api_job_timeline(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return JsonResponse({"events": [
        {"time": e.created_at.isoformat(), "kind": e.kind, "description": e.description,
         "user": str(e.user) if e.user else None, "notes": e.notes}
        for e in job.events.select_related("user")
    ]})


@worker_or_staff_required
def api_board(request):
    """Active jobs grouped by status for the live kanban board."""
    return JsonResponse({"board": selectors.board_payload()})


@staff_required
def api_alerts(request):
    jobs = selectors.jobs_needing_alert()
    return JsonResponse({"count": jobs.count(), "jobs": [
        {"id": j.pk, "plate": j.vehicle.plate_number, "customer": j.customer.name} for j in jobs
    ]})


@login_required
def service_photo(request, pk, line_pk):
    """
    Job photos show customers' cars, so they are NOT public files.
    Allowed: staff, workers, and the customer who owns the job. Everyone else gets a 404.
    """
    line = get_object_or_404(JobService.objects.select_related("job__customer"), pk=line_pk, job_id=pk)
    user = request.user
    owner = user.is_customer and line.job.customer.user_id == user.pk
    if not (user.is_staff_role or user.is_worker or owner) or not line.photo:
        raise Http404
    return FileResponse(line.photo.open("rb"))
