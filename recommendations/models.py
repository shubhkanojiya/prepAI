"""Personalised recommendations generated from activity and performance."""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TimeStampedModel


class Recommendation(TimeStampedModel):
    class Type(models.TextChoices):
        TEST = "test", "Practice test"
        PAPER = "paper", "Question paper"
        MATERIAL = "material", "Study material"
        CHAPTER = "chapter", "Chapter to revise"
        QUESTION = "question", "Practice question"
        REVISION = "revision", "Revision topic"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="recommendations")
    rec_type = models.CharField(max_length=15, choices=Type.choices, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(max_length=255)
    score = models.FloatField(default=0, help_text="Higher = more relevant")
    is_dismissed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-score", "-created_at"]
        indexes = [models.Index(fields=["user", "is_dismissed", "-score"])]
        constraints = [
            models.UniqueConstraint(fields=["user", "content_type", "object_id"],
                                    name="unique_recommendation"),
        ]

    def __str__(self):
        return f"{self.user} · {self.get_rec_type_display()} · {self.reason}"
