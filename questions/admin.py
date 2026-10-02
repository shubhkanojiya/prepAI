from django.contrib import admin
from django.db.models import Count

from core.admin_mixins import PublishableAdminMixin

from .models import Concept, Question, QuestionAppearance, QuestionOption


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 4
    fields = ["order", "text", "is_correct"]


class QuestionAppearanceInline(admin.TabularInline):
    model = QuestionAppearance
    extra = 0
    fields = ["paper", "year", "question_number", "marks"]
    autocomplete_fields = ["paper"]
    verbose_name = "historical appearance"
    verbose_name_plural = "historical appearances (used for frequency analysis)"


@admin.register(Question)
class QuestionAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["short_text", "subject", "chapter", "question_type", "difficulty", "marks",
                    "appearance_count", "is_important", "is_published"]
    list_filter = ["subject__class_level__board", "subject__class_level", "question_type",
                   "difficulty", "source", "is_important", "is_published", "is_sample"]
    search_fields = ["text", "answer", "subject__name", "chapter__name"]
    autocomplete_fields = ["subject", "chapter", "topic", "concepts"]
    list_select_related = ["subject__class_level", "chapter"]
    inlines = [QuestionOptionInline, QuestionAppearanceInline]
    fieldsets = [
        (None, {"fields": ["subject", "chapter", "topic", "question_type", "text", "image"]}),
        ("Answer", {"fields": ["answer", "explanation", "numeric_tolerance"]}),
        ("Scoring & metadata", {"fields": ["difficulty", "marks", "negative_marks", "concepts",
                                           "source", "is_important"]}),
        ("Publishing", {"fields": ["is_published", "is_sample"]}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_appearances=Count("appearances"))

    @admin.display(description="Question")
    def short_text(self, obj):
        return obj.text[:90]

    @admin.display(description="Appearances", ordering="_appearances")
    def appearance_count(self, obj):
        return obj._appearances


@admin.register(Concept)
class ConceptAdmin(admin.ModelAdmin):
    list_display = ["name", "subject"]
    list_filter = ["subject__class_level__board"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["subject"]


@admin.register(QuestionAppearance)
class QuestionAppearanceAdmin(admin.ModelAdmin):
    """Historical question frequency data."""

    list_display = ["question", "paper", "year", "question_number", "marks"]
    list_filter = ["year", "paper__subject__class_level__board", "paper__subject"]
    search_fields = ["question__text", "paper__title"]
    autocomplete_fields = ["question", "paper"]
    list_select_related = ["question", "paper"]
