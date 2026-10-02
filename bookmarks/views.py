from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.filters import paginate

from . import services
from .models import Bookmark


@login_required
def bookmark_list(request):
    kind = request.GET.get("kind", "")
    q = request.GET.get("q", "").strip().lower()
    qs = (Bookmark.objects.filter(user=request.user)
          .select_related("content_type").prefetch_related("content_object"))
    if kind in ("paper", "previous_year"):
        qs = qs.filter(content_type=services.content_type_for_kind("paper"))
    elif kind in services.KINDS:
        qs = qs.filter(content_type=services.content_type_for_kind(kind))

    items = []
    for bookmark in qs:
        obj = bookmark.content_object
        if obj is None:
            continue
        obj_kind = services.kind_for_object(obj)
        is_pyp = obj_kind == "paper" and getattr(obj, "is_previous_year", False)
        if kind == "previous_year" and not is_pyp:
            continue
        if kind == "paper" and is_pyp:
            continue
        title = getattr(obj, "title", None) or getattr(obj, "text", "")
        if q and q not in title.lower():
            continue
        items.append({"bookmark": bookmark, "object": obj, "kind": obj_kind, "title": title,
                      "is_pyp": is_pyp,
                      "icon": "clock-history" if is_pyp else services.KINDS[obj_kind][3]})

    tabs = [("", "All", "bookmarks"), ("question", "Questions", "question-circle"),
            ("paper", "Question papers", "file-earmark-text"),
            ("previous_year", "Previous years", "clock-history"),
            ("material", "Study material", "journal-text"), ("test", "Tests", "clipboard-check")]
    return render(request, "bookmarks/bookmark_list.html", {
        "page_obj": paginate(request, items, 15), "kind": kind, "q": q, "tabs": tabs,
    })
