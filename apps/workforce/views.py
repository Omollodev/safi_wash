from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.permissions import role_required, staff_required

from . import selectors
from .forms import WorkerForm
from .models import WorkerProfile


@staff_required
def worker_list(request):
    return render(request, "workforce/worker_list.html", {"workers": selectors.workers_with_stats()})


@staff_required
def worker_detail(request, pk):
    worker = get_object_or_404(WorkerProfile.objects.select_related("user"), pk=pk)
    return render(
        request,
        "workforce/worker_detail.html",
        {
            "worker": worker,
            "busy": selectors.is_busy(worker),
            "recent_jobs": worker.assigned_jobs.select_related("vehicle").order_by("-created_at")[:10],
        },
    )


@staff_required
def worker_edit(request, pk):
    worker = get_object_or_404(WorkerProfile, pk=pk)
    form = WorkerForm(request.POST or None, instance=worker)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Worker updated.")
        return redirect("workforce:detail", pk=pk)
    return render(request, "workforce/worker_form.html", {"form": form, "worker": worker})


@staff_required
@require_POST
def worker_toggle_availability(request, pk):
    worker = get_object_or_404(WorkerProfile, pk=pk)
    worker.is_available = not worker.is_available
    worker.save(update_fields=["is_available"])
    messages.success(request, f"{worker} is now {'available' if worker.is_available else 'unavailable'}.")
    return redirect("workforce:detail", pk=pk)


@role_required("worker")
def my_jobs(request):
    profile = getattr(request.user, "worker_profile", None)
    jobs = profile.assigned_jobs.select_related("vehicle", "customer") if profile else []
    active = [j for j in jobs if j.status in ("waiting", "in_progress", "awaiting_extra")]
    today = timezone.localdate()
    done_today = [
        j for j in jobs
        if j.status == "completed" and j.completed_at and timezone.localtime(j.completed_at).date() == today
    ]
    return render(request, "workforce/my_jobs.html", {"profile": profile, "active": active, "done_today": done_today})


@staff_required
def api_available_workers(request):
    data = [{"id": w.pk, "name": w.name, "rating": str(w.rating)} for w in selectors.available_workers()]
    return JsonResponse({"results": data})
