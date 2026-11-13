from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("profile/", views.profile, name="profile"),
    path("vehicles/new/", views.vehicle_add, name="vehicle_add"),
    path("book/", views.book, name="book"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
]
