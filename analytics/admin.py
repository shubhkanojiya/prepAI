from django.contrib import admin

from .models import PerformanceRecord, UserActivity


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ["user", "activity_type", "description", "created_at"]
    list_filter = ["activity_type", "created_at"]
    search_fields = ["user__email", "description"]
    list_select_related = ["user"]
    date_hierarchy = "created_at"


@admin.register(PerformanceRecord)
class PerformanceRecordAdmin(admin.ModelAdmin):
    list_display = ["user", "subject", "chapter", "test_type", "attempted", "correct",
                    "incorrect", "skipped", "recorded_on"]
    list_filter = ["test_type", "subject__class_level__board", "recorded_on"]
    search_fields = ["user__email", "subject__name", "chapter__name"]
    list_select_related = ["user", "subject", "chapter"]
    date_hierarchy = "recorded_on"
