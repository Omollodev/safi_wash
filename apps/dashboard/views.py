import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.core.permissions import staff_required

from . import selectors


def _jsonld():
    """Structured data so Google can show the business (name, phone, address)."""
    b = settings.BUSINESS
    data = {
        "@context": "https://schema.org",
        "@type": "AutoWash",
        "name": b["name"],
        "telephone": b["phone"],
        "email": b["email"],
        "address": {"@type": "PostalAddress", "streetAddress": b["address"]},
    }
    # "<" escaped so the JSON can never close the <script> tag early.
    return json.dumps(data).replace("<", "\\u003c")


def landing(request):
    """Public home page."""
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    photos = selectors.landing_photos()
    categories = selectors.landing_services()
    return render(
        request,
        "dashboard/landing.html",
        {
            "categories": categories,
            "service_count": sum(len(c["services"]) for c in categories),
            "hero_photo": photos["hero"],
            "gallery": photos["gallery"],
            "stats": selectors.landing_stats(),
            "jsonld": _jsonld(),
        },
    )


@login_required
def home(request):
    """Sends each role to the right start page."""
    role = request.user.role
    if role == "customer":
        return redirect("portal:home")
    if role == "worker":
        return redirect("workforce:my_jobs")
    return render(request, "dashboard/home.html", {"stats": selectors.overview()})


@staff_required
def reports(request):
    return render(
        request,
        "dashboard/reports.html",
        {
            "today": selectors.period_report(0),
            "week": selectors.period_report(6),
            "month": selectors.period_report(29),
            "top_workers": selectors.top_workers(),
            "services": selectors.popular_services(),
            "methods": selectors.payment_methods(),
        },
    )


@staff_required
def api_stats(request):
    stats = selectors.overview()
    stats["collected_today"] = str(stats["collected_today"])
    return JsonResponse(stats)
