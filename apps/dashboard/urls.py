from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("dashboard/", views.home, name="home"),
    path("reports/", views.reports, name="reports"),
    path("dashboard/api/stats/", views.api_stats, name="api_stats"),
]
