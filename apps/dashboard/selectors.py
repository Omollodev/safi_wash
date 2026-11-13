"""Numbers for the dashboard and reports -- all aggregated in the database."""
import re
from datetime import timedelta
from itertools import groupby

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.catalog.models import GalleryPhoto, Service
from apps.core.templatetags.money import minutes, money
from apps.customers.models import Customer
from apps.jobs import selectors as job_selectors
from apps.jobs.models import Job, JobEvent, JobService
from apps.payments.models import Payment
from apps.workforce.models import WorkerProfile


def _period_start(days: int):
    return timezone.localdate() - timedelta(days=days)


def overview():
    today = timezone.localdate()
    counts = dict(Job.objects.filter(status__in=["waiting", "in_progress", "awaiting_extra"])
                  .values_list("status").annotate(n=Count("id")).order_by())
    return {
        "waiting": counts.get("waiting", 0),
        "in_progress": counts.get("in_progress", 0),
        "awaiting_extra": counts.get("awaiting_extra", 0),
        "completed_today": Job.objects.filter(status="completed", completed_at__date=today).count(),
        "collected_today": Payment.objects.filter(created_at__date=today).aggregate(t=Sum("amount"))["t"] or 0,
        "alerts": Job.objects.filter(need_alert=True, status__in=["in_progress", "awaiting_extra"]).count(),
        "workers_available": WorkerProfile.objects.filter(is_available=True, user__is_active=True).count(),
        "workers_total": WorkerProfile.objects.filter(user__is_active=True).count(),
    }


def period_report(days: int):
    """days=0 -> today, 6 -> last 7 days, 29 -> last 30 days."""
    start = _period_start(days)
    done = Job.objects.filter(status="completed", completed_at__date__gte=start)
    return {
        "jobs": done.count(),
        "billed": done.aggregate(t=Sum("total_price"))["t"] or 0,
        "collected": Payment.objects.filter(created_at__date__gte=start).aggregate(t=Sum("amount"))["t"] or 0,
        "avg_minutes": round(done.aggregate(a=Avg("actual_duration"))["a"] or 0),
    }


def top_workers(days: int = 29, limit: int = 5):
    start = _period_start(days)
    return (
        WorkerProfile.objects.select_related("user")
        .annotate(done=Count("assigned_jobs", filter=Q(assigned_jobs__status="completed", assigned_jobs__completed_at__date__gte=start)))
        .filter(done__gt=0)
        .order_by("-done")[:limit]
    )


def popular_services(days: int = 29, limit: int = 8):
    start = _period_start(days)
    return (
        JobService.objects.filter(job__created_at__date__gte=start)
        .values("service__name")
        .annotate(times=Count("id"), revenue=Sum("price"))
        .order_by("-times")[:limit]
    )


def payment_methods(days: int = 29):
    start = _period_start(days)
    return (
        Payment.objects.filter(created_at__date__gte=start, amount__gt=0)
        .values("method").annotate(total=Sum("amount"), n=Count("id")).order_by("-total")
    )


# ---------------------------------------------------------------- staff dashboard
def _trend(today, yesterday):
    """
    A trend badge only when there is something real to compare with: no yesterday figure, no arrow.
    Returns None, or {"direction": "up"|"down"|"flat", "pct": int}.
    """
    if not yesterday:
        return None
    change = (float(today) - float(yesterday)) / float(yesterday) * 100
    pct = round(abs(change))
    if pct == 0:
        return {"direction": "flat", "pct": 0}
    return {"direction": "up" if change > 0 else "down", "pct": pct}


def kpis():
    """The four headline cards: value, a supporting line and (when real data exists) a trend."""
    now = timezone.now()
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    stats = overview()

    oldest_waiting = Job.objects.filter(status="waiting").order_by("created_at").values_list("created_at", flat=True).first()
    busy = (Job.objects.filter(status__in=["in_progress", "awaiting_extra"], assigned_worker__isnull=False)
            .values("assigned_worker").distinct().count())
    done_yesterday = Job.objects.filter(status="completed", completed_at__date=yesterday).count()
    paid_today = Payment.objects.filter(created_at__date=today).aggregate(t=Sum("amount"), n=Count("id"))
    collected_yesterday = Payment.objects.filter(created_at__date=yesterday).aggregate(t=Sum("amount"))["t"] or 0
    return {
        **stats,
        "waiting_minutes": int((now - oldest_waiting).total_seconds() // 60) if oldest_waiting else None,
        "workers_busy": busy,
        "avg_minutes": period_report(0)["avg_minutes"],
        "payments_today": paid_today["n"] or 0,
        "completed_trend": _trend(stats["completed_today"], done_yesterday),
        "collected_trend": _trend(stats["collected_today"], collected_yesterday),
    }


def revenue_series(days: int = 7):
    """
    Money collected per day (refunds count as negative), newest day last, with the bar geometry
    for the SVG chart. Days without payments are real zeros, not gaps.
    """
    days = 30 if days == 30 else 7
    start = timezone.localdate() - timedelta(days=days - 1)
    rows = (Payment.objects.filter(created_at__date__gte=start)
            .annotate(day=TruncDate("created_at")).values("day").annotate(total=Sum("amount")).order_by())
    totals = {row["day"]: row["total"] for row in rows}
    points = []
    for i in range(days):
        day = start + timedelta(days=i)
        points.append({"date": day, "value": totals.get(day, 0)})

    values = [max(float(p["value"]), 0) for p in points]
    top = max(values) if values else 0
    # round the axis maximum up to a "nice" number (1, 2, 2.5, 5 x 10^n) so the grid lines read well
    nice = 1
    if top > 0:
        import math
        mag = 10 ** math.floor(math.log10(top))
        nice = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= top)
    w, h, left, bottom, top_pad = 560, 220, 52, 28, 10
    plot_w, plot_h = w - left - 8, h - bottom - top_pad
    slot = plot_w / days
    bar = max(min(slot * 0.62, 44), 6)
    for i, p in enumerate(points):
        height = round(values[i] / nice * plot_h, 1) if top > 0 else 0
        p.update({
            "x": round(left + slot * i + (slot - bar) / 2, 1), "w": round(bar, 1),
            "h": height, "y": round(top_pad + plot_h - height, 1),
            "cx": round(left + slot * i + slot / 2, 1),
            "label": p["date"].strftime("%a") if days == 7 else (p["date"].strftime("%d") if i % 3 == 0 or i == days - 1 else ""),
            "is_today": i == days - 1,
        })
    ticks = [{"y": round(top_pad + plot_h - plot_h * f, 1), "value": nice * f} for f in (0, 0.5, 1)] if top > 0 else []
    total = sum(float(p["value"]) for p in points)
    return {
        "days": days, "points": points, "ticks": ticks, "has_data": top > 0,
        "total": sum(p["value"] for p in points), "average": total / days,
        "w": w, "h": h, "left": left, "plot_bottom": top_pad + plot_h, "plot_right": w - 8,
        "best": max(points, key=lambda p: p["value"]) if top > 0 else None,
    }


EVENT_ICONS = {
    "created": "clipboard-plus", "status_change": "refresh-cw", "worker_assigned": "user-check",
    "extra_service_added": "circle-plus", "service_completed": "circle-check", "service_reopened": "rotate-ccw",
    "edited": "square-pen", "payment_cash": "wallet", "payment_mpesa": "smartphone", "refund": "rotate-ccw",
    "mpesa_requested": "smartphone", "mpesa_failed": "triangle-alert",
}


_STATUS_WORDS = re.compile(r"\b(" + "|".join(Job.Status.values) + r")\b")


def _readable(text: str) -> str:
    """'Status changed from in_progress to awaiting_extra' -> '... from In progress to Awaiting extra services'."""
    labels = dict(Job.Status.choices)
    return _STATUS_WORDS.sub(lambda m: labels[m.group(1)].lower(), text)


def recent_activity(limit: int = 8):
    events = JobEvent.objects.select_related("job__vehicle", "user").order_by("-created_at", "-id")[:limit]
    return [{
        "icon": EVENT_ICONS.get(e.kind, "activity"), "text": _readable(e.description), "job_id": e.job_id,
        "plate": e.job.vehicle.plate_number, "who": str(e.user) if e.user else "System", "at": e.created_at,
        "alert": e.kind == "mpesa_failed",
    } for e in events]


def recent_transactions(limit: int = 6):
    return Payment.objects.select_related("job__vehicle", "job__customer").order_by("-created_at", "-id")[:limit]


def worker_status(limit: int = 8):
    """Who is free, busy (and on which job) or off duty. One query for workers, one for their active jobs."""
    workers = list(WorkerProfile.objects.filter(user__is_active=True).select_related("user"))
    active = (Job.objects.filter(status__in=["in_progress", "awaiting_extra"], assigned_worker__in=workers)
              .select_related("vehicle").order_by("started_at"))
    on_job = {}
    for job in active:
        on_job.setdefault(job.assigned_worker_id, job)
    rows = []
    for w in workers:
        job = on_job.get(w.pk)
        state = "busy" if job else ("available" if w.is_available else "off")
        rows.append({"worker": w, "state": state, "job": job})
    order = {"busy": 0, "available": 1, "off": 2}
    rows.sort(key=lambda r: (order[r["state"]], r["worker"].name))
    return {"rows": rows[:limit], "more": max(len(rows) - limit, 0), "total": len(rows)}


def kpi_cards(stats):
    """The four headline cards as plain data, so the template is one reusable partial in a loop."""
    wait, busy, total = stats["waiting_minutes"], stats["workers_busy"], stats["workers_total"]
    return [
        {"stat": "waiting", "label": "Waiting", "icon": "clock", "tone": "neutral", "value": stats["waiting"],
         "hint": f"Longest wait {minutes(wait)}" if stats["waiting"] and wait is not None else "The queue is clear"},
        {"stat": "in_progress", "label": "In progress", "icon": "droplets", "tone": "blue", "value": stats["in_progress"],
         "hint": f"{busy} of {total} workers busy" if total else "No workers added yet"},
        {"stat": "completed_today", "label": "Done today", "icon": "circle-check", "tone": "green", "value": stats["completed_today"],
         "hint": f"Average {minutes(stats['avg_minutes'])} per job" if stats["completed_today"] and stats["avg_minutes"] else "No jobs finished yet today",
         "trend": stats["completed_trend"]},
        {"stat": "collected_today", "label": "Collected today", "icon": "wallet", "tone": "amber", "value": money(stats["collected_today"]),
         "hint": (f"From {stats['payments_today']} payment{'s' if stats['payments_today'] != 1 else ''}" if stats["payments_today"] else "No payments yet today"),
         "trend": stats["collected_trend"]},
    ]


def dashboard(range_days: int = 7):
    """Everything the staff dashboard shows, from real records only."""
    stats = kpis()
    return {
        "stats": stats,
        "cards": kpi_cards(stats),
        "board": job_selectors.board_payload(),
        "revenue": revenue_series(range_days),
        "activity": recent_activity(),
        "transactions": recent_transactions(),
        "team": worker_status(),
    }


# ---------------------------------------------------------------- public landing page
CATEGORY_ICONS = {  # Lucide icon names shown on the landing page tabs and cards
    "exterior": "droplets",
    "interior": "wind",
    "detailing": "sparkles",
    "additional": "circle-plus",
}


def landing_services():
    """Active services grouped by category, in the order the categories are defined."""
    order = [value for value, _ in Service.Category.choices]
    services = sorted(Service.objects.filter(is_active=True), key=lambda s: (order.index(s.category), s.display_order, s.name))
    labels = dict(Service.Category.choices)
    return [
        {"key": key, "label": labels[key], "icon": CATEGORY_ICONS.get(key, "droplet"), "services": list(items)}
        for key, items in groupby(services, key=lambda s: s.category)
    ]


def landing_photos():
    photos = list(GalleryPhoto.objects.filter(is_active=True))
    featured = sorted((p for p in photos if p.is_featured), key=lambda p: p.created_at, reverse=True)
    return {"hero": featured[0] if featured else None, "gallery": photos}


def landing_stats():
    """Only REAL numbers from the database. Zero values are dropped, so a new shop shows nothing fake."""
    stats = [
        ("Car washed", "Cars washed", Job.objects.filter(status="completed").count()),
        ("Happy customer", "Happy customers", Customer.objects.filter(is_active=True).count()),
        ("Service on offer", "Services on offer", Service.objects.filter(is_active=True).count()),
        ("Team member", "Team members", WorkerProfile.objects.filter(user__is_active=True).count()),
    ]
    return [{"label": one if value == 1 else many, "value": value} for one, many, value in stats if value > 0]
