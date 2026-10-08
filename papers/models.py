"""Question papers and previous-year papers."""
from django.db import models
from django.urls import reverse

from core.models import PublishableModel, PublishableQuerySet
from core.validators import validate_pdf


class QuestionPaper(PublishableModel):
    class PaperType(models.TextChoices):
        PREVIOUS_YEAR = "previous_year", "Previous year paper"
        SAMPLE = "sample", "Sample paper"
        MODEL = "model", "Model paper"
        PRACTICE = "practice", "Practice paper"
        CHAPTER_WISE = "chapter_wise", "Chapter-wise paper"
        PRE_BOARD = "pre_board", "Pre-board paper"

    class ExamType(models.TextChoices):
        ANNUAL = "annual", "Annual / main examination"
        SUPPLEMENTARY = "supplementary", "Supplementary / compartment"
        TERM_1 = "term_1", "Term 1"
        TERM_2 = "term_2", "Term 2"
        PRE_BOARD = "pre_board", "Pre-board"
        OTHER = "other", "Other"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    subject = models.ForeignKey("boards.Subject", on_delete=models.CASCADE, related_name="papers")
    chapter = models.ForeignKey("boards.Chapter", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="papers", help_text="Only for chapter-wise papers")
    paper_type = models.CharField(max_length=20, choices=PaperType.choices,
                                  default=PaperType.SAMPLE, db_index=True)
    exam_type = models.CharField(max_length=20, choices=ExamType.choices, default=ExamType.ANNUAL)
    year = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices,
                                  default=Difficulty.MEDIUM)
    description = models.TextField(blank=True)
    pdf = models.FileField(upload_to="papers/%Y/", validators=[validate_pdf], blank=True)
    solution_pdf = models.FileField(upload_to="papers/solutions/%Y/", validators=[validate_pdf],
                                    blank=True)
    total_marks = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(default=0, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    download_count = models.PositiveIntegerField(default=0, editable=False)

    objects = PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["-year", "-created_at"]
        indexes = [
            models.Index(fields=["paper_type", "year"]),
            models.Index(fields=["subject", "paper_type", "is_published"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pdf:
            try:
                self.file_size = self.pdf.size
            except (OSError, ValueError):
                pass
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("papers:detail", args=[self.slug])

    @property
    def is_previous_year(self):
        return self.paper_type == self.PaperType.PREVIOUS_YEAR

    EXAM_SHORT_LABELS = {"annual": "Main", "supplementary": "Supp.", "term_1": "Term 1",
                         "term_2": "Term 2", "pre_board": "Pre-board", "other": "Other"}

    @property
    def exam_short_label(self):
        return self.EXAM_SHORT_LABELS.get(self.exam_type, self.get_exam_type_display())


class PreviousYearPaperManager(models.Manager.from_queryset(PublishableQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR)


class PreviousYearPaper(QuestionPaper):
    """Proxy giving previous-year papers their own admin section and manager."""

    objects = PreviousYearPaperManager()

    class Meta:
        proxy = True
        verbose_name = "previous year paper"
        verbose_name_plural = "previous year papers"

    def save(self, *args, **kwargs):
        self.paper_type = QuestionPaper.PaperType.PREVIOUS_YEAR
        super().save(*args, **kwargs)
