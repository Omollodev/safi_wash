from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve


def healthz(request):
    """Used by Docker/hosting health checks. Reveals nothing, touches nothing."""
    return HttpResponse("ok", content_type="text/plain")


def gallery_media(request, path):
    """Public gallery images only. MEDIA_ROOT is read per request so tests/deploys can change it."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("", include("apps.dashboard.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("customers/", include("apps.customers.urls")),
    path("services/", include("apps.catalog.urls")),
    path("workers/", include("apps.workforce.urls")),
    path("jobs/", include("apps.jobs.urls")),
    path("payments/", include("apps.payments.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("portal/", include("apps.portal.urls")),
    # ONLY the public gallery is served straight from disk. Job photos (customers' cars)
    # go through a permission-checked view instead: see jobs:service_photo.
    re_path(r"^media/(?P<path>gallery/.*)$", gallery_media),
]
