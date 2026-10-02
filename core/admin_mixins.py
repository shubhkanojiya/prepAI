"""Reusable admin behaviour for publishable content."""
from django.contrib import admin, messages


class PublishableAdminMixin:
    """Adds publish/unpublish bulk actions and standard publish filters."""

    actions = ["publish_selected", "unpublish_selected"]

    @admin.action(description="Publish selected items")
    def publish_selected(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f"{updated} item(s) published.", messages.SUCCESS)

    @admin.action(description="Unpublish selected items")
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated} item(s) unpublished.", messages.WARNING)
