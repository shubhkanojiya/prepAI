from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from content.models import StudyMaterial
from papers.models import PreviousYearPaper, QuestionPaper

from .models import Announcement, Notification
from .services import notify_users, students_for_board, students_for_subject


def _notify_new_content(instance, notification_type, label):
    if not instance.is_published:
        return
    notify_users(
        students_for_subject(instance.subject),
        notification_type,
        f"New {label}: {instance.title}",
        f"{instance.subject.name} · {instance.subject.class_level}",
        instance.get_absolute_url(),
    )


@receiver(post_save, sender=StudyMaterial)
def material_published(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        _notify_new_content(instance, Notification.Type.MATERIAL, "study material")


@receiver(post_save, sender=QuestionPaper)
@receiver(post_save, sender=PreviousYearPaper)
def paper_published(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        _notify_new_content(instance, Notification.Type.PAPER, "question paper")


@receiver(post_save, sender=Announcement)
def announcement_published(sender, instance, raw=False, **kwargs):
    if raw or not instance.is_published or instance.sent_at:
        return
    notify_users(students_for_board(instance.board), Notification.Type.ANNOUNCEMENT,
                 instance.title, instance.message, instance.url)
    Announcement.objects.filter(pk=instance.pk).update(sent_at=timezone.now())
