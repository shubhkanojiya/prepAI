"""Abstract base models shared across PrepAI apps."""
from django.db import models


class TimeStampedModel(models.Model):
    """Adds created/updated timestamps to every model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublishableQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class PublishableModel(TimeStampedModel):
    """
    Content that administrators can publish/unpublish.

    `is_sample` flags demo/seed content so the UI can clearly label it and it
    is never mistaken for real examination material.
    """

    is_published = models.BooleanField(default=True, db_index=True)
    is_sample = models.BooleanField(
        default=False,
        help_text="Demo/sample content created for development. Shown with a 'Sample' badge.",
    )

    objects = PublishableQuerySet.as_manager()

    class Meta:
        abstract = True
