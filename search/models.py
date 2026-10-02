from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class SearchHistory(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
                             blank=True, related_name="searches")
    query = models.CharField(max_length=255)
    normalized_query = models.CharField(max_length=255, db_index=True)
    filters = models.JSONField(default=dict, blank=True)
    results_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "search history"
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return self.query
