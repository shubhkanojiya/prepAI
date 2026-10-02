from django.contrib import admin

from core.admin_mixins import PublishableAdminMixin
from questions.models import QuestionAppearance

from .models import PreviousYearPaper, QuestionPaper


class PaperQuestionInline(admin.TabularInline):
    model = QuestionAppearance
    extra = 0
    fields = ["question", "question_number", "year", "marks"]
    autocomplete_fields = ["question"]
    verbose_name = "question in this paper"
    verbose_name_plural = "questions in this paper (feeds frequency analysis)"


class BasePaperAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["title", "subject", "paper_type", "year", "exam_type", "download_count",
                    "is_sample", "is_published"]
    list_filter = ["subject__class_level__board", "subject__class_level", "paper_type", "year",
                   "exam_type", "difficulty", "is_published", "is_sample"]
    search_fields = ["title", "description", "subject__name"]
    prepopulated_fields = {"slug": ["title"]}
    autocomplete_fields = ["subject", "chapter"]
    list_select_related = ["subject__class_level__board"]
    readonly_fields = ["file_size", "view_count", "download_count"]
    inlines = [PaperQuestionInline]


@admin.register(QuestionPaper)
class QuestionPaperAdmin(BasePaperAdmin):
    pass


@admin.register(PreviousYearPaper)
class PreviousYearPaperAdmin(BasePaperAdmin):
    exclude = ["paper_type"]
