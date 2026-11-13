from django.urls import path

from . import views

app_name = "workforce"

urlpatterns = [
    path("", views.worker_list, name="list"),
    path("my-jobs/", views.my_jobs, name="my_jobs"),
    path("<int:pk>/", views.worker_detail, name="detail"),
    path("<int:pk>/edit/", views.worker_edit, name="edit"),
    path("<int:pk>/toggle-availability/", views.worker_toggle_availability, name="toggle_availability"),
    path("api/available/", views.api_available_workers, name="api_available"),
]
