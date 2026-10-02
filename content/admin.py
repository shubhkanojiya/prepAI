from django.contrib import admin

from core.admin_mixins import PublishableAdminMixin

from .models import StudyMaterial


@admin.register(StudyMaterial)
class StudyMaterialAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["title", "material_type", "subject", "chapter", "is_featured", "view_count",
                    "is_sample", "is_published"]
    list_filter = ["material_type", "subject__class_level__board", "subject__class_level",
                   "is_featured", "is_published", "is_sample"]
    list_editable = ["is_featured"]
    search_fields = ["title", "summary", "body"]
    prepopulated_fields = {"slug": ["title"]}
    autocomplete_fields = ["subject", "chapter", "topic"]
    list_select_related = ["subject__class_level", "chapter"]
    readonly_fields = ["view_count", "download_count"]
