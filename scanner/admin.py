from django.contrib import admin

from .models import ScannerHistory


@admin.register(ScannerHistory)
class ScannerHistoryAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "status", "detected_subject_name", "processing_ms",
                    "created_at"]
    list_filter = ["status", "is_handwritten"]
    search_fields = ["user__email", "detected_question", "typed_question"]
    list_select_related = ["user"]
    readonly_fields = ["processing_ms", "error_message"]
