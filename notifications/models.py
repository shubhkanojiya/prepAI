"""In-app notifications and admin announcements."""
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Notification(TimeStampedModel):
    class Type(models.TextChoices):
        MATERIAL = "material", "New study material"
        PAPER = "paper", "New question paper"
        TEST_RECOMMENDATION = "test_recommendation", "Recommended test"
        TEST_REMINDER = "test_reminder", "Test reminder"
        PERFORMANCE = "performance", "Performance update"
        ANNOUNCEMENT = "announcement", "Announcement"

    TYPE_ICONS = {
        "material": "journal-text",
        "paper": "file-earmark-text",
        "test_recommendation": "clipboard-check",
        "test_reminder": "alarm",
        "performance": "graph-up-arrow",
        "announcement": "megaphone",
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notifications")
    notification_type = models.CharField(max_length=25, choices=Type.choices, db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]

    def __str__(self):
        return f"{self.user} · {self.title}"

    @property
    def icon(self):
        return self.TYPE_ICONS.get(self.notification_type, "bell")


class Announcement(TimeStampedModel):
    """
    Platform-wide announcement. Saving a *published* announcement fans out a
    Notification to every active user (optionally limited to one board).
    """

    title = models.CharField(max_length=200)
    message = models.TextField()
    url = models.CharField(max_length=300, blank=True)
    board = models.ForeignKey("boards.Board", on_delete=models.CASCADE, null=True, blank=True,
                              help_text="Leave empty to notify all students")
    is_published = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
