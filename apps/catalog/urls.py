from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.service_list, name="list"),
    path("new/", views.service_create, name="create"),
    path("<int:pk>/edit/", views.service_edit, name="edit"),
    path("<int:pk>/toggle/", views.service_toggle, name="toggle"),
    path("<int:pk>/delete/", views.service_delete, name="delete"),
    path("api/", views.api_service_list, name="api_list"),
]
