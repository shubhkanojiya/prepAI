from django.contrib import admin

from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ["query", "user", "results_count", "created_at"]
    search_fields = ["query", "user__email"]
    list_filter = ["created_at"]
    list_select_related = ["user"]
