"""Tiny factory helpers shared by the test files (keeps each test short and readable)."""
from decimal import Decimal
from itertools import count

from django.contrib.auth import get_user_model

from apps.catalog.models import Service
from apps.customers.models import Customer, Vehicle
from apps.workforce.services import ensure_worker_profile

User = get_user_model()
_n = count(1)
PASSWORD = "Test-pass-12345!"


def make_user(role="customer", **extra):
    i = next(_n)
    user = User.objects.create_user(
        username=f"{role}{i}", password=PASSWORD, role=role, email=f"{role}{i}@example.com",
        first_name=role.title(), phone="0712345678", **extra,
    )
    if role == "worker":
        ensure_worker_profile(user)
    return user


def make_customer(with_login=False):
    i = next(_n)
    user = make_user("customer") if with_login else None
    customer = Customer.objects.create(user=user, name=f"Customer {i}", phone="0712345678")
    vehicle = Vehicle.objects.create(customer=customer, plate_number=f"K{i:03d}ABC", make="Toyota", model="Axio")
    return customer, vehicle


def make_service(name=None, category="exterior", price="500", minutes=20):
    i = next(_n)
    return Service.objects.create(
        name=name or f"Service {i}", category=category, price=Decimal(price), estimated_duration=minutes
    )
