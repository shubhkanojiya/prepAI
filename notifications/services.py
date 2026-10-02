"""
Notification helpers.

Fan-out uses bulk_create in batches. At large scale, move `notify_users`
into a background worker (Celery/RQ) — callers don't need to change.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Notification

BATCH_SIZE = 1000


def notify(user, notification_type, title, message="", url=""):
    return Notification.objects.create(
        user=user, notification_type=notification_type, title=title[:200],
        message=message, url=url[:300],
    )


def notify_users(user_ids, notification_type, title, message="", url=""):
    batch, created = [], 0
    for user_id in user_ids:
        batch.append(Notification(user_id=user_id, notification_type=notification_type,
                                  title=title[:200], message=message, url=url[:300]))
        if len(batch) >= BATCH_SIZE:
            Notification.objects.bulk_create(batch)
            created += len(batch)
            batch = []
    if batch:
        Notification.objects.bulk_create(batch)
        created += len(batch)
    return created


def students_for_subject(subject):
    """Active students whose profile matches the subject's board (and class, if set)."""
    class_level = subject.class_level
    return (
        get_user_model().objects.filter(is_active=True, profile__board_id=class_level.board_id)
        .filter(Q(profile__class_level__isnull=True) | Q(profile__class_level_id=class_level.id))
        .values_list("id", flat=True)
    )


def students_for_board(board=None):
    users = get_user_model().objects.filter(is_active=True)
    if board is not None:
        users = users.filter(profile__board=board)
    return users.values_list("id", flat=True)
