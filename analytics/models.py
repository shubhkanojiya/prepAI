"""User activity log and per-attempt performance records."""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TimeStampedModel


class UserActivity(TimeStampedModel):
    class Type(models.TextChoices):
        LOGIN = "login", "Signed in"
        VIEW_PAPER = "view_paper", "Viewed paper"
        DOWNLOAD_PAPER = "download_paper", "Downloaded paper"
        VIEW_MATERIAL = "view_material", "Viewed study material"
        VIEW_QUESTION = "view_question", "Viewed question"
        VIEW_CHAPTER = "view_chapter", "Viewed chapter"
        START_TEST = "start_test", "Started test"
        SUBMIT_TEST = "submit_test", "Submitted test"
        SCAN = "scan", "Scanned a question"
        ASK_AI = "ask_ai", "Asked the AI assistant"
        SEARCH = "search", "Searched"
        BOOKMARK = "bookmark", "Bookmarked"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="activities")
    activity_type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    url = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "user activities"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "activity_type"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.get_activity_type_display()}"


class PerformanceRecord(TimeStampedModel):
    """Aggregated result of one attempt for one chapter (or subject when no chapter)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="performance_records")
    attempt = models.ForeignKey("testengine.TestAttempt", on_delete=models.CASCADE,
                                related_name="performance_records")
    subject = models.ForeignKey("boards.Subject", on_delete=models.CASCADE,
                                related_name="performance_records")
    chapter = models.ForeignKey("boards.Chapter", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="performance_records")
    test_type = models.CharField(max_length=20, db_index=True)
    total_questions = models.PositiveSmallIntegerField(default=0)
    attempted = models.PositiveSmallIntegerField(default=0)
    correct = models.PositiveSmallIntegerField(default=0)
    incorrect = models.PositiveSmallIntegerField(default=0)
    skipped = models.PositiveSmallIntegerField(default=0)
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    time_seconds = models.PositiveIntegerField(default=0)
    recorded_on = models.DateField(db_index=True)

    class Meta:
        ordering = ["-recorded_on"]
        indexes = [
            models.Index(fields=["user", "subject"]),
            models.Index(fields=["user", "chapter"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.subject} · {self.recorded_on}"

    @property
    def accuracy(self):
        return round(100 * self.correct / self.attempted, 1) if self.attempted else 0.0
