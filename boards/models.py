"""
Board → Class → Subject → Chapter → Topic hierarchy.

Everything is data-driven: new boards, classes, subjects, chapters and topics
are created in Django Admin without code changes.
"""
from django.db import models
from django.urls import reverse

from core.models import PublishableModel


class Board(PublishableModel):
    class BoardType(models.TextChoices):
        NATIONAL = "national", "National board"
        STATE = "state", "State board"
        INTERNATIONAL = "international", "International board"

    name = models.CharField(max_length=150, unique=True)
    short_name = models.CharField(max_length=30, help_text="e.g. CBSE, ICSE, MSBSHSE")
    slug = models.SlugField(max_length=160, unique=True)
    board_type = models.CharField(max_length=20, choices=BoardType.choices, default=BoardType.STATE)
    state = models.CharField(max_length=80, blank=True, help_text="State/region for state boards")
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="boards/logos/", blank=True)
    website = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False, db_index=True,
                                      help_text="Show on the homepage 'Popular boards' section")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.short_name or self.name

    def get_absolute_url(self):
        return reverse("boards:board_detail", args=[self.slug])


class ClassLevel(PublishableModel):
    """A class/grade within a board (e.g. CBSE Class 10)."""

    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="classes")
    name = models.CharField(max_length=60, help_text="e.g. Class 10")
    number = models.PositiveSmallIntegerField(help_text="Numeric grade, used for ordering")
    slug = models.SlugField(max_length=80)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["board", "order", "number"]
        verbose_name = "class"
        verbose_name_plural = "classes"
        constraints = [
            models.UniqueConstraint(fields=["board", "slug"], name="unique_class_slug_per_board"),
        ]

    def __str__(self):
        return f"{self.board} · {self.name}"

    def get_absolute_url(self):
        return reverse("boards:class_detail", args=[self.board.slug, self.slug])


class Subject(PublishableModel):
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    code = models.CharField(max_length=20, blank=True, help_text="Official subject code, if any")
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="book",
                            help_text="Bootstrap Icons name, e.g. calculator, flask, globe")
    color = models.CharField(max_length=7, default="#0f766e", help_text="Accent colour (hex)")
    is_popular = models.BooleanField(default=False, db_index=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["class_level", "order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["class_level", "slug"], name="unique_subject_slug_per_class"),
        ]

    def __str__(self):
        return f"{self.name} ({self.class_level})"

    @property
    def board(self):
        return self.class_level.board

    def get_absolute_url(self):
        cl = self.class_level
        return reverse("boards:subject_detail", args=[cl.board.slug, cl.slug, self.slug])


class Chapter(PublishableModel):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="chapters")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["subject", "order", "number", "name"]
        constraints = [
            models.UniqueConstraint(fields=["subject", "slug"], name="unique_chapter_slug_per_subject"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        s = self.subject
        cl = s.class_level
        return reverse("boards:chapter_detail", args=[cl.board.slug, cl.slug, s.slug, self.slug])


class Topic(PublishableModel):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["chapter", "order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["chapter", "slug"], name="unique_topic_slug_per_chapter"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        ch = self.chapter
        s = ch.subject
        cl = s.class_level
        return reverse("boards:topic_detail",
                       args=[cl.board.slug, cl.slug, s.slug, ch.slug, self.slug])
