from django.contrib import admin

from .models import AIConversation, AIMessage


class AIMessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0
    fields = ["role", "content", "model_name", "input_tokens", "output_tokens", "created_at"]
    readonly_fields = fields
    can_delete = False


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "mode", "is_archived", "updated_at"]
    list_filter = ["mode", "is_archived"]
    search_fields = ["title", "user__email"]
    list_select_related = ["user"]
    inlines = [AIMessageInline]
