from django.contrib import admin

from .models import Announcement, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "notification_type", "title", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["user__email", "title", "message"]
    list_select_related = ["user"]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "board", "is_published", "sent_at", "created_at"]
    list_filter = ["is_published", "board"]
    search_fields = ["title", "message"]
    readonly_fields = ["sent_at"]
    autocomplete_fields = ["board"]
    help_text = "Publishing an announcement sends a notification to all matching students once."
