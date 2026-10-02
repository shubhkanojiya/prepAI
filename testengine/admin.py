from django.contrib import admin
from django.db.models import Count

from core.admin_mixins import PublishableAdminMixin

from .models import Test, TestAnswer, TestAttempt, TestQuestion


class TestQuestionInline(admin.TabularInline):
    model = TestQuestion
    extra = 1
    fields = ["order", "question", "marks", "negative_marks"]
    autocomplete_fields = ["question"]


@admin.register(Test)
class TestAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["title", "test_type", "subject", "chapter", "duration_minutes",
                    "question_total", "is_featured", "is_published"]
    list_filter = ["test_type", "difficulty", "board", "class_level", "is_featured",
                   "is_published", "is_sample"]
    search_fields = ["title", "description"]
    prepopulated_fields = {"slug": ["title"]}
    autocomplete_fields = ["board", "class_level", "subject", "chapter", "paper"]
    inlines = [TestQuestionInline]
    fieldsets = [
        (None, {"fields": ["title", "slug", "test_type", "difficulty", "description",
                           "instructions"]}),
        ("Scope", {"fields": ["board", "class_level", "subject", "chapter", "paper"],
                   "description": "Set the most specific level; broader levels are filled in "
                                  "automatically."}),
        ("Rules", {"fields": ["duration_minutes", "pass_percentage", "shuffle_questions",
                              "show_explanations", "max_attempts"]}),
        ("Publishing", {"fields": ["is_featured", "is_published", "is_sample"]}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_questions=Count("test_questions"))

    @admin.display(description="Questions", ordering="_questions")
    def question_total(self, obj):
        return obj._questions


class TestAnswerInline(admin.TabularInline):
    model = TestAnswer
    extra = 0
    can_delete = False
    fields = ["test_question", "text_answer", "is_marked_for_review", "is_correct",
              "marks_awarded", "time_spent_seconds"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "status", "percentage", "accuracy", "started_at",
                    "submitted_at"]
    list_filter = ["status", "test__test_type"]
    search_fields = ["user__email", "test__title"]
    list_select_related = ["user", "test"]
    readonly_fields = [f.name for f in TestAttempt._meta.fields]
    inlines = [TestAnswerInline]

    def has_add_permission(self, request):
        return False
