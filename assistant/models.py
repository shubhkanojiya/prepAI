from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class AIConversation(TimeStampedModel):
    class Mode(models.TextChoices):
        GENERAL = "general", "General help"
        SIMPLE = "simple", "Explain simply"
        DETAILED = "detailed", "Detailed explanation"
        PRACTICE = "practice", "Practice questions"
        QUIZ = "quiz", "Quiz me"
        REVISION = "revision", "Revision assistant"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="ai_conversations")
    title = models.CharField(max_length=200, default="New conversation")
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.GENERAL)
    subject = models.ForeignKey("boards.Subject", on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="ai_conversations")
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "AI conversation"
        indexes = [models.Index(fields=["user", "is_archived", "-updated_at"])]

    def __str__(self):
        return self.title


class AIMessage(TimeStampedModel):
    class Role(models.TextChoices):
        USER = "user", "Student"
        ASSISTANT = "assistant", "PrepAI"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE,
                                     related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    model_name = models.CharField(max_length=60, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "AI message"

    def __str__(self):
        return f"{self.role}: {self.content[:60]}"
