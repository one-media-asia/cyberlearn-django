from django.contrib import admin
from .models import TrialUsage


@admin.register(TrialUsage)
class TrialUsageAdmin(admin.ModelAdmin):
    list_display = ("session_key", "prompts_used", "paid_access", "created_at", "updated_at")
    list_filter = ("paid_access", "created_at")
    search_fields = ("session_key",)
    readonly_fields = ("session_key", "created_at", "updated_at")
# Register your models here.
