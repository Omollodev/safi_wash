from decimal import Decimal

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def money(value):
    """{{ job.total_price|money }}  ->  KES 1,500.00"""
    try:
        value = Decimal(value or 0)
    except Exception:
        value = Decimal(0)
    return f"{settings.BUSINESS['currency']} {value:,.2f}"


@register.filter
def minutes(value):
    """{{ 95|minutes }} -> 1h 35m"""
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        return "-"
    hours, mins = divmod(value, 60)
    return f"{hours}h {mins}m" if hours else f"{mins}m"


@register.filter
def tel(value):
    """+254 712 345 678 -> +254712345678 (safe for tel: links)"""
    return "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")


@register.filter
def wa_number(value):
    """0712 345 678 / +254712345678 -> 254712345678 (the format wa.me links need)"""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    return digits
