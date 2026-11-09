from django.contrib import messages
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permissions import staff_required, worker_or_staff_required

from .forms import ServiceForm
from .models import Service


@staff_required
def service_list(request):
    services = Service.objects.all()
    category = request.GET.get("category")
    if category:
        services = services.filter(category=category)
    return render(
        request,
        "catalog/service_list.html",
        {"services": services, "categories": Service.Category.choices, "current": category},
    )


@staff_required
def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Service created.")
        return redirect("catalog:list")
    return render(request, "catalog/service_form.html", {"form": form, "title": "New service"})


@staff_required
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Service updated.")
        return redirect("catalog:list")
    return render(request, "catalog/service_form.html", {"form": form, "title": f"Edit {service}"})


@staff_required
@require_POST
def service_toggle(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.is_active = not service.is_active
    service.save(update_fields=["is_active"])
    messages.success(request, f"{service} is now {'active' if service.is_active else 'hidden'}.")
    return redirect("catalog:list")


@staff_required
@require_POST
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    try:
        service.delete()
        messages.success(request, "Service deleted.")
    except ProtectedError:
        messages.error(request, "This service is used by existing jobs. Hide it instead of deleting.")
    return redirect("catalog:list")


@worker_or_staff_required
def api_service_list(request):
    data = [
        {"id": s.pk, "name": s.name, "price": str(s.price), "duration": s.estimated_duration,
         "category": s.category, "is_extra": s.is_extra}
        for s in Service.objects.filter(is_active=True)
    ]
    return JsonResponse({"results": data})
