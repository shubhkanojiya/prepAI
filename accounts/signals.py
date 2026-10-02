from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    from analytics.services import log_activity
    from analytics.models import UserActivity

    log_activity(user, UserActivity.Type.LOGIN, "Signed in")
