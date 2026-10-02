"""Bookmark registry and helpers."""
from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from .models import Bookmark

# kind → (app_label, model_name, label, icon). Previous-year papers are
# QuestionPapers; they're distinguished by paper_type when filtering.
KINDS = {
    "question": ("questions", "question", "Questions", "question-circle"),
    "paper": ("papers", "questionpaper", "Question papers", "file-earmark-text"),
    "material": ("content", "studymaterial", "Study material", "journal-text"),
    "test": ("testengine", "test", "Tests", "clipboard-check"),
}


class BookmarkError(Exception):
    pass


def model_for_kind(kind):
    if kind not in KINDS:
        raise BookmarkError("Unknown bookmark type.")
    app_label, model_name, *_ = KINDS[kind]
    return apps.get_model(app_label, model_name)


def content_type_for_kind(kind):
    return ContentType.objects.get_for_model(model_for_kind(kind))


def kind_for_object(obj):
    ct = ContentType.objects.get_for_model(obj)  # proxies resolve to the concrete model
    for kind, (app_label, model_name, *_rest) in KINDS.items():
        if ct.app_label == app_label and ct.model == model_name:
            return kind
    return None


def toggle(user, kind, object_id):
    """Add the bookmark if missing, remove it if present. Returns True when now bookmarked."""
    model = model_for_kind(kind)
    manager = model.objects
    queryset = manager.published() if hasattr(manager, "published") else manager.all()
    if not queryset.filter(pk=object_id).exists():
        raise BookmarkError("That item no longer exists.")
    ct = ContentType.objects.get_for_model(model)
    deleted, _ = Bookmark.objects.filter(user=user, content_type=ct, object_id=object_id).delete()
    if deleted:
        return False
    Bookmark.objects.create(user=user, content_type=ct, object_id=object_id)
    from analytics.models import UserActivity
    from analytics.services import log_activity

    log_activity(user, UserActivity.Type.BOOKMARK, f"Bookmarked a {kind}",
                 obj=queryset.get(pk=object_id))
    return True


def bookmarked_ids(request, model):
    """Set of bookmarked object ids for `model` — one query per model per request."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return set()
    cache = request.__dict__.setdefault("_bookmark_cache", {})
    ct = ContentType.objects.get_for_model(model)
    if ct.id not in cache:
        cache[ct.id] = set(Bookmark.objects.filter(user=user, content_type=ct)
                           .values_list("object_id", flat=True))
    return cache[ct.id]
