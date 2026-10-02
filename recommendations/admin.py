from django.contrib import admin

from .models import Recommendation


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ["user", "rec_type", "content_object", "reason", "score", "is_dismissed",
                    "created_at"]
    list_filter = ["rec_type", "is_dismissed"]
    search_fields = ["user__email", "reason"]
    list_select_related = ["user", "content_type"]
