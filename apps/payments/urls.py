from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("jobs/<int:job_pk>/cash/", views.cash_payment, name="cash"),
    path("jobs/<int:job_pk>/refund/", views.refund, name="refund"),
    path("jobs/<int:job_pk>/mpesa/", views.mpesa_start, name="mpesa_start"),
    path("mpesa/<int:pk>/status/", views.mpesa_status, name="mpesa_status"),
    path("mpesa/<int:pk>/simulate/", views.mpesa_simulate, name="mpesa_simulate"),
    path("mpesa/callback/<str:token>/", views.mpesa_callback, name="mpesa_callback"),
]
