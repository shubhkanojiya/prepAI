"""Online tests, attempts and answers."""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import PublishableModel, TimeStampedModel


class Test(PublishableModel):
    class TestType(models.TextChoices):
        CHAPTER = "chapter", "Chapter test"
        SUBJECT = "subject", "Subject test"
        BOARD = "board", "Board test"
        PREVIOUS_YEAR = "previous_year", "Previous year test"
        PRACTICE = "practice", "Practice test"
        MOCK = "mock", "Full-length mock test"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text="Shown before the test starts (Markdown)")
    test_type = models.CharField(max_length=20, choices=TestType.choices,
                                 default=TestType.PRACTICE, db_index=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices,
                                  default=Difficulty.MEDIUM)
    board = models.ForeignKey("boards.Board", on_delete=models.CASCADE, null=True, blank=True,
                              related_name="tests")
    class_level = models.ForeignKey("boards.ClassLevel", on_delete=models.CASCADE, null=True,
                                    blank=True, related_name="tests", verbose_name="class")
    subject = models.ForeignKey("boards.Subject", on_delete=models.CASCADE, null=True, blank=True,
                                related_name="tests")
    chapter = models.ForeignKey("boards.Chapter", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="tests")
    paper = models.ForeignKey("papers.QuestionPaper", on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="tests",
                              help_text="Source paper for previous-year tests")
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    pass_percentage = models.PositiveSmallIntegerField(default=33)
    shuffle_questions = models.BooleanField(default=False)
    show_explanations = models.BooleanField(default=True)
    max_attempts = models.PositiveSmallIntegerField(default=0, help_text="0 = unlimited")
    is_featured = models.BooleanField(default=False, db_index=True)
    questions = models.ManyToManyField("questions.Question", through="TestQuestion",
                                       related_name="tests")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["test_type", "is_published"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("testengine:detail", args=[self.slug])

    def save(self, *args, **kwargs):
        # Derive the hierarchy from the most specific level provided.
        if self.chapter_id and not self.subject_id:
            self.subject = self.chapter.subject
        if self.subject_id and not self.class_level_id:
            self.class_level = self.subject.class_level
        if self.class_level_id and not self.board_id:
            self.board = self.class_level.board
        super().save(*args, **kwargs)


class TestQuestion(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="test_questions")
    question = models.ForeignKey("questions.Question", on_delete=models.CASCADE,
                                 related_name="test_links")
    order = models.PositiveSmallIntegerField(default=0)
    marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                help_text="Override the question's default marks")
    negative_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["test", "question"], name="unique_question_per_test"),
        ]

    def __str__(self):
        return f"{self.test} · Q{self.order}"

    @property
    def effective_marks(self):
        return self.marks if self.marks is not None else self.question.marks

    @property
    def effective_negative_marks(self):
        return self.negative_marks if self.negative_marks is not None else self.question.negative_marks


class TestAttempt(TimeStampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        AUTO_SUBMITTED = "auto_submitted", "Auto-submitted (time up)"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="test_attempts")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="attempts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS,
                              db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    question_order = models.JSONField(default=list, help_text="TestQuestion ids in display order")
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    percentage = models.FloatField(default=0)
    accuracy = models.FloatField(default=0)
    correct_count = models.PositiveSmallIntegerField(default=0)
    incorrect_count = models.PositiveSmallIntegerField(default=0)
    unanswered_count = models.PositiveSmallIntegerField(default=0)
    ungraded_count = models.PositiveSmallIntegerField(
        default=0, help_text="Subjective answers not auto-graded"
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-started_at"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.test} · {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.deadline:
            self.deadline = self.started_at + timedelta(minutes=self.test.duration_minutes)
        super().save(*args, **kwargs)

    @property
    def is_in_progress(self):
        return self.status == self.Status.IN_PROGRESS

    @property
    def remaining_seconds(self):
        return max(0, int((self.deadline - timezone.now()).total_seconds()))

    @property
    def passed(self):
        return self.percentage >= self.test.pass_percentage

    def get_absolute_url(self):
        if self.is_in_progress:
            return reverse("testengine:attempt", args=[self.pk])
        return reverse("testengine:result", args=[self.pk])


class TestAnswer(TimeStampedModel):
    attempt = models.ForeignKey(TestAttempt, on_delete=models.CASCADE, related_name="answers")
    test_question = models.ForeignKey(TestQuestion, on_delete=models.CASCADE,
                                      related_name="answers")
    selected_options = models.ManyToManyField("questions.QuestionOption", blank=True)
    text_answer = models.TextField(blank=True)
    is_marked_for_review = models.BooleanField(default=False)
    visited = models.BooleanField(default=False)
    is_correct = models.BooleanField(null=True, help_text="Null = unanswered or not auto-graded")
    marks_awarded = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["attempt", "test_question__order"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "test_question"],
                                    name="unique_answer_per_question"),
        ]

    def __str__(self):
        return f"Answer {self.pk} ({self.attempt_id})"
