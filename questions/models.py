"""
Question bank and historical-occurrence tracking.

`QuestionAppearance` records every time a question appeared in a stored
paper. Frequency analysis (questions/services/frequency.py) is computed
exclusively from these records — never invented.
"""
from django.db import models
from django.urls import reverse

from core.models import PublishableModel, TimeStampedModel
from core.utils import text_fingerprint
from core.validators import validate_image


class Concept(TimeStampedModel):
    """A reusable concept tag (e.g. Force, Acceleration) used to link similar questions."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    subject = models.ForeignKey("boards.Subject", on_delete=models.CASCADE, related_name="concepts")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["subject", "slug"], name="unique_concept_per_subject"),
        ]

    def __str__(self):
        return self.name


class Question(PublishableModel):
    class Type(models.TextChoices):
        MCQ = "mcq", "Multiple choice (single answer)"
        MULTI = "multi", "Multiple choice (multiple answers)"
        TRUE_FALSE = "true_false", "True / False"
        NUMERIC = "numeric", "Numerical answer"
        FILL_BLANK = "fill_blank", "Fill in the blank"
        SHORT = "short", "Short answer"
        LONG = "long", "Long answer"

    OBJECTIVE_TYPES = {Type.MCQ, Type.MULTI, Type.TRUE_FALSE}
    AUTO_GRADED_TYPES = OBJECTIVE_TYPES | {Type.NUMERIC, Type.FILL_BLANK}

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class Source(models.TextChoices):
        MANUAL = "manual", "Created by editor"
        PREVIOUS_YEAR = "previous_year", "From a previous-year paper"
        AI = "ai", "AI generated (reviewed)"

    subject = models.ForeignKey("boards.Subject", on_delete=models.CASCADE, related_name="questions")
    chapter = models.ForeignKey("boards.Chapter", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="questions")
    topic = models.ForeignKey("boards.Topic", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="questions")
    question_type = models.CharField(max_length=12, choices=Type.choices, default=Type.MCQ)
    text = models.TextField("question")
    image = models.ImageField(upload_to="questions/%Y/", blank=True, validators=[validate_image])
    answer = models.TextField(
        blank=True,
        help_text="Model answer. For numeric questions the number; for fill-in-the-blank, "
                  "accepted answers separated by '|'.",
    )
    explanation = models.TextField(blank=True, help_text="Step-by-step explanation (Markdown)")
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices,
                                  default=Difficulty.MEDIUM, db_index=True)
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    negative_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    numeric_tolerance = models.FloatField(default=0.01,
                                          help_text="Allowed absolute error for numeric answers")
    concepts = models.ManyToManyField(Concept, blank=True, related_name="questions")
    source = models.CharField(max_length=15, choices=Source.choices, default=Source.MANUAL)
    is_important = models.BooleanField(default=False, db_index=True,
                                       help_text="Editor-marked important question")
    fingerprint = models.CharField(max_length=64, db_index=True, editable=False,
                                   help_text="Hash of normalized text for repeat detection")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subject", "chapter", "is_published"]),
            models.Index(fields=["question_type", "difficulty"]),
        ]

    def __str__(self):
        return self.text[:80]

    def save(self, *args, **kwargs):
        self.fingerprint = text_fingerprint(self.text)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("questions:detail", args=[self.pk])

    @property
    def is_auto_graded(self):
        return self.question_type in self.AUTO_GRADED_TYPES

    @property
    def is_objective(self):
        return self.question_type in self.OBJECTIVE_TYPES


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class QuestionAppearance(TimeStampedModel):
    """One historical occurrence of a question in a stored examination paper."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="appearances")
    paper = models.ForeignKey("papers.QuestionPaper", on_delete=models.CASCADE,
                              related_name="appearances")
    year = models.PositiveSmallIntegerField(
        db_index=True, help_text="Examination year (copied from the paper when blank)"
    )
    question_number = models.CharField(max_length=20, blank=True)
    marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-year"]
        indexes = [models.Index(fields=["question", "year"])]
        constraints = [
            models.UniqueConstraint(fields=["question", "paper"], name="unique_question_per_paper"),
        ]

    def __str__(self):
        return f"{self.question} — {self.year}"

    def save(self, *args, **kwargs):
        if not self.year and self.paper_id and self.paper.year:
            self.year = self.paper.year
        super().save(*args, **kwargs)
