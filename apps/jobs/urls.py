from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.job_list, name="list"),
    path("new/", views.job_create, name="create"),
    path("<int:pk>/", views.job_detail, name="detail"),
    path("<int:pk>/edit/", views.job_edit, name="edit"),
    path("<int:pk>/print/", views.job_print, name="print"),
    path("<int:pk>/status/", views.job_change_status, name="change_status"),
    path("<int:pk>/assign/", views.job_assign_worker, name="assign_worker"),
    path("<int:pk>/add-service/", views.job_add_service, name="add_service"),
    path("<int:pk>/cancel/", views.job_cancel, name="cancel"),
    path("<int:pk>/services/<int:line_pk>/complete/", views.service_complete, name="service_complete"),
    path("<int:pk>/services/<int:line_pk>/reopen/", views.service_uncomplete, name="service_uncomplete"),
    path("<int:pk>/services/<int:line_pk>/photo/", views.service_photo, name="service_photo"),
    # JSON API
    path("api/board/", views.api_board, name="api_board"),
    path("api/alerts/", views.api_alerts, name="api_alerts"),
    path("api/<int:pk>/", views.api_job_detail, name="api_detail"),
    path("api/<int:pk>/timeline/", views.api_job_timeline, name="api_timeline"),
]
