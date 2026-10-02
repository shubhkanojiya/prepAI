"""Generic bookmarks for questions, papers, study materials and tests."""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TimeStampedModel


class Bookmark(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="bookmarks")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "content_type"])]
        constraints = [
            models.UniqueConstraint(fields=["user", "content_type", "object_id"],
                                    name="unique_bookmark"),
        ]

    def __str__(self):
        return f"{self.user} → {self.content_type.model}:{self.object_id}"
