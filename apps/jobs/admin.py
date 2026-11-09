from django.contrib import admin

from .models import Job, JobEvent, JobService


class JobServiceInline(admin.TabularInline):
    model = JobService
    extra = 0


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "customer", "status", "priority", "total_price", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("vehicle__plate_number", "customer__name")
    inlines = [JobServiceInline]


admin.site.register(JobEvent)
