"""Write-side business logic for customers and their vehicles."""
from django.db import transaction

from .models import Customer, Vehicle


def ensure_customer_for_user(user) -> Customer:
    """Make sure a portal user has a Customer record (create or link one)."""
    customer = Customer.objects.filter(user=user).first()
    if customer:
        return customer
    return Customer.objects.create(
        user=user,
        name=user.get_full_name() or user.username,
        phone=user.phone or "",
        email=user.email,
    )


@transaction.atomic
def create_customer_with_vehicle(customer_data: dict, vehicle_data: dict) -> tuple[Customer, Vehicle]:
    """Used by the 'quick add' form at the counter: one step, both records."""
    customer = Customer.objects.create(**customer_data)
    vehicle = Vehicle.objects.create(customer=customer, **vehicle_data)
    return customer, vehicle
