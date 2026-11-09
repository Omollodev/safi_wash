from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("new/", views.customer_create, name="create"),
    path("quick-add/", views.quick_add, name="quick_add"),
    path("<int:pk>/", views.customer_detail, name="detail"),
    path("<int:pk>/edit/", views.customer_edit, name="edit"),
    path("<int:customer_pk>/vehicles/new/", views.vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="vehicle_detail"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
    path("api/customers/", views.api_customer_search, name="api_customers"),
    path("api/vehicles/", views.api_vehicle_search, name="api_vehicles"),
    path("api/<int:customer_pk>/vehicles/", views.api_customer_vehicles, name="api_customer_vehicles"),
]
