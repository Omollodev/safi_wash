"""Staff-facing customer & vehicle screens (the customer self-service portal is in apps/portal)."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import staff_required, worker_or_staff_required

from . import selectors, services
from .forms import CustomerForm, QuickAddForm, VehicleForm
from .models import Customer, Vehicle


@staff_required
def customer_list(request):
    q = request.GET.get("q", "")
    page = Paginator(selectors.search_customers(q, only_active=False), 20).get_page(request.GET.get("page"))
    return render(request, "customers/customer_list.html", {"page": page, "q": q})


@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    jobs = customer.jobs.select_related("vehicle").order_by("-created_at")[:10]
    return render(
        request,
        "customers/customer_detail.html",
        {"customer": customer, "vehicles": customer.vehicles.all(), "jobs": jobs},
    )


@staff_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        messages.success(request, "Customer created. Now add their vehicle.")
        return redirect("customers:vehicle_create", customer_pk=customer.pk)
    return render(request, "customers/customer_form.html", {"form": form, "title": "New customer"})


@staff_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer updated.")
        return redirect("customers:detail", pk=pk)
    return render(request, "customers/customer_form.html", {"form": form, "title": f"Edit {customer}"})


@staff_required
def vehicle_create(request, customer_pk):
    customer = get_object_or_404(Customer, pk=customer_pk)
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.customer = customer
        vehicle.save()
        messages.success(request, f"{vehicle.plate_number} added.")
        return redirect("customers:detail", pk=customer.pk)
    return render(
        request, "customers/vehicle_form.html", {"form": form, "customer": customer, "title": "Add vehicle"}
    )


@staff_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vehicle updated.")
        return redirect("customers:detail", pk=vehicle.customer_id)
    return render(
        request,
        "customers/vehicle_form.html",
        {"form": form, "customer": vehicle.customer, "title": f"Edit {vehicle.plate_number}"},
    )


@worker_or_staff_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle.objects.select_related("customer"), pk=pk)
    return render(
        request,
        "customers/vehicle_detail.html",
        {"vehicle": vehicle, "jobs": vehicle.jobs.order_by("-created_at")[:20]},
    )


@staff_required
def quick_add(request):
    form = QuickAddForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer_data, vehicle_data = form.split()
        customer, vehicle = services.create_customer_with_vehicle(customer_data, vehicle_data)
        messages.success(request, "Customer and vehicle created. Start the job now.")
        return redirect(f"/jobs/new/?vehicle={vehicle.pk}")
    return render(request, "customers/quick_add.html", {"form": form})


# ---------------------------------------------------------------- tiny JSON API for the job form
@staff_required
def api_customer_search(request):
    customers = selectors.search_customers(request.GET.get("q", ""))[:10]
    return JsonResponse({"results": [{"id": c.pk, "name": c.name, "phone": c.phone} for c in customers]})


@staff_required
def api_vehicle_search(request):
    vehicles = selectors.search_vehicles(request.GET.get("q", ""))[:10]
    return JsonResponse(
        {"results": [{"id": v.pk, "label": str(v), "customer": v.customer.name} for v in vehicles]}
    )


@staff_required
def api_customer_vehicles(request, customer_pk):
    vehicles = Vehicle.objects.filter(customer_id=customer_pk, is_active=True)
    return JsonResponse({"results": [{"id": v.pk, "label": str(v)} for v in vehicles]})
