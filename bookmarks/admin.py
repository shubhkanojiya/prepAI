from django.contrib import admin

from .models import Bookmark


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ["user", "content_type", "object_id", "content_object", "created_at"]
    list_filter = ["content_type"]
    search_fields = ["user__email", "note"]
    list_select_related = ["user", "content_type"]
