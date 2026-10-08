from django.conf import settings
from django.core.cache import cache


def site(request):
    """Global template context: branding, nav boards, theme and unread count."""
    nav_boards = cache.get("nav_boards")
    if nav_boards is None:
        from boards.models import Board

        nav_boards = list(
            Board.objects.published().order_by("order", "name").values("name", "slug", "short_name")[:12]
        )
        cache.set("nav_boards", nav_boards, 600)

    context = {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "nav_boards": nav_boards,
        # The button links to allauth's route, so it needs allauth installed as well as a client ID.
        "google_auth_enabled": bool(settings.GOOGLE_OAUTH_CLIENT_ID) and "allauth" in settings.INSTALLED_APPS,
        "MAX_IMAGE_UPLOAD_MB": settings.MAX_IMAGE_UPLOAD_MB,
        "user_theme": "system",
        "unread_notifications": 0,
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, "profile", None)
        if profile is not None:
            context["user_theme"] = profile.theme
        context["unread_notifications"] = user.notifications.filter(is_read=False).count()
    return context
