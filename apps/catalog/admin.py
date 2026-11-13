from django.contrib import admin

from .models import GalleryPhoto, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "estimated_duration", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name",)


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(admin.ModelAdmin):
    list_display = ("title", "is_featured", "is_active", "display_order", "created_at")
    list_editable = ("is_featured", "is_active", "display_order")
