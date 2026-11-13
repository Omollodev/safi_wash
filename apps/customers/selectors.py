"""Read-side queries for customers (selectors never change data)."""
from django.db.models import Q

from .models import Customer, Vehicle


def search_customers(term: str = "", only_active: bool = True):
    qs = Customer.objects.all()
    if only_active:
        qs = qs.filter(is_active=True)
    term = (term or "").strip()
    if term:
        qs = qs.filter(
            Q(name__icontains=term)
            | Q(phone__icontains=term)
            | Q(email__icontains=term)
            | Q(vehicles__plate_number__icontains=term)
        ).distinct()
    return qs


def search_vehicles(term: str = ""):
    qs = Vehicle.objects.select_related("customer").filter(is_active=True)
    term = (term or "").strip()
    if term:
        qs = qs.filter(
            Q(plate_number__icontains=term)
            | Q(make__icontains=term)
            | Q(model__icontains=term)
            | Q(customer__name__icontains=term)
        )
    return qs
