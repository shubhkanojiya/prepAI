"""Study material library."""
from django.db import models
from django.urls import reverse

from core.models import PublishableModel
from core.validators import validate_image, validate_pdf


class StudyMaterial(PublishableModel):
    class MaterialType(models.TextChoices):
        PDF = "pdf", "PDF"
        NOTES = "notes", "Notes"
        SUMMARY = "summary", "Chapter summary"
        REVISION = "revision", "Revision notes"
        FORMULA = "formula", "Formula sheet"
        IMPORTANT_QUESTIONS = "important_questions", "Important questions"
        CONCEPT = "concept", "Concept explanation"

    TYPE_ICONS = {
        "pdf": "file-earmark-pdf",
        "notes": "journal-text",
        "summary": "card-text",
        "revision": "arrow-repeat",
        "formula": "calculator",
        "important_questions": "star",
        "concept": "lightbulb",
    }

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    material_type = models.CharField(max_length=25, choices=MaterialType.choices,
                                     default=MaterialType.NOTES, db_index=True)
    subject = models.ForeignKey("boards.Subject", on_delete=models.CASCADE,
                                related_name="materials")
    chapter = models.ForeignKey("boards.Chapter", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="materials")
    topic = models.ForeignKey("boards.Topic", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="materials")
    summary = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True, help_text="Content in Markdown (headings, lists, **bold**)")
    file = models.FileField(upload_to="materials/%Y/", blank=True, validators=[validate_pdf])
    thumbnail = models.ImageField(upload_to="materials/thumbs/", blank=True,
                                  validators=[validate_image])
    reading_minutes = models.PositiveSmallIntegerField(default=5)
    is_featured = models.BooleanField(default=False, db_index=True)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    download_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["subject", "chapter", "material_type"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("content:detail", args=[self.slug])

    @property
    def icon(self):
        return self.TYPE_ICONS.get(self.material_type, "file-earmark-text")
