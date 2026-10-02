"""Custom user (email login) and student profile."""
import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models

from core.models import TimeStampedModel
from core.validators import validate_image


class PrepAIUserManager(UserManager):
    """Email is the login identifier; a username is generated when omitted."""

    def _unique_username(self, email):
        base = (email.split("@")[0] or "student")[:20]
        username = base
        while self.model.objects.filter(username=username).exists():
            username = f"{base}{uuid.uuid4().hex[:6]}"
        return username

    def create_user(self, email=None, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        username = extra_fields.pop("username", None) or self._unique_username(email)
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        email = self.normalize_email(email).lower()
        username = extra_fields.pop("username", None) or self._unique_username(email)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = PrepAIUserManager()

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def display_name(self):
        return self.first_name or self.get_full_name() or self.email.split("@")[0]


class Profile(TimeStampedModel):
    class Theme(models.TextChoices):
        SYSTEM = "system", "Match my device"
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        HINDI = "hi", "Hindi"
        MARATHI = "mr", "Marathi"
        GUJARATI = "gu", "Gujarati"
        TAMIL = "ta", "Tamil"
        TELUGU = "te", "Telugu"
        KANNADA = "kn", "Kannada"
        BENGALI = "bn", "Bengali"

    class ExplanationStyle(models.TextChoices):
        SIMPLE = "simple", "Simple, short explanations"
        DETAILED = "detailed", "Detailed, step-by-step explanations"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    board = models.ForeignKey("boards.Board", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="students")
    class_level = models.ForeignKey("boards.ClassLevel", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="students", verbose_name="class")
    subjects = models.ManyToManyField("boards.Subject", blank=True, related_name="students")
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, validators=[validate_image])
    phone = models.CharField(max_length=20, blank=True)
    school = models.CharField(max_length=200, blank=True)
    preferred_language = models.CharField(max_length=5, choices=Language.choices,
                                          default=Language.ENGLISH)
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.SYSTEM)
    explanation_style = models.CharField(max_length=10, choices=ExplanationStyle.choices,
                                         default=ExplanationStyle.DETAILED)
    daily_goal_minutes = models.PositiveSmallIntegerField(default=60)
    exam_date = models.DateField(null=True, blank=True, help_text="Your board exam start date")
    email_notifications = models.BooleanField(default=True)

    def __str__(self):
        return f"Profile of {self.user}"
