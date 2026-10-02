from django.conf import settings
from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel
from core.validators import validate_image


class ScannerHistory(TimeStampedModel):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="scans")
    image = models.ImageField(upload_to="scans/%Y/%m/", blank=True, validators=[validate_image])
    typed_question = models.TextField(blank=True, help_text="Question typed instead of scanned")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROCESSING,
                              db_index=True)
    extracted_text = models.TextField(blank=True)
    detected_question = models.TextField(blank=True)
    detected_subject_name = models.CharField(max_length=120, blank=True)
    detected_topic_name = models.CharField(max_length=200, blank=True)
    subject = models.ForeignKey("boards.Subject", on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="scans")
    chapter = models.ForeignKey("boards.Chapter", on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="scans")
    is_handwritten = models.BooleanField(default=False)
    answer = models.TextField(blank=True)
    steps = models.JSONField(default=list, blank=True)
    concept = models.TextField(blank=True)
    follow_up_questions = models.JSONField(default=list, blank=True)
    error_message = models.CharField(max_length=300, blank=True)
    processing_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "scanner history"
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return (self.detected_question or self.typed_question or "Scan")[:80]

    def get_absolute_url(self):
        return reverse("scanner:detail", args=[self.pk])
