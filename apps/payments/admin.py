from django.contrib import admin

from .models import MpesaRequest, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "amount", "method", "reference", "created_at")
    list_filter = ("method",)


@admin.register(MpesaRequest)
class MpesaRequestAdmin(admin.ModelAdmin):
    list_display = ("checkout_request_id", "job", "amount", "status", "created_at")
    list_filter = ("status",)
