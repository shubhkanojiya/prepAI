"""Shared helpers for list pages: hierarchy filters and pagination."""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

from boards.models import Board, Chapter, ClassLevel, Subject


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def apply_hierarchy_filters(request, queryset, subject_path="subject", chapter_path="chapter"):
    """
    Apply ?board=&class_level=&subject=&chapter= filters and return
    (queryset, context) where context feeds templates/components/filter_bar.html.
    """
    board = to_int(request.GET.get("board"))
    class_level = to_int(request.GET.get("class_level"))
    subject = to_int(request.GET.get("subject"))
    chapter = to_int(request.GET.get("chapter"))

    if board:
        queryset = queryset.filter(**{f"{subject_path}__class_level__board_id": board})
    if class_level:
        queryset = queryset.filter(**{f"{subject_path}__class_level_id": class_level})
    if subject:
        queryset = queryset.filter(**{f"{subject_path}_id": subject})
    if chapter and chapter_path:
        queryset = queryset.filter(**{f"{chapter_path}_id": chapter})

    context = {
        "filter_boards": Board.objects.published().only("id", "short_name", "name"),
        "filter_classes": ClassLevel.objects.published().filter(board_id=board) if board else [],
        "filter_subjects": (Subject.objects.published().filter(class_level_id=class_level)
                            if class_level else []),
        "filter_chapters": (Chapter.objects.published().filter(subject_id=subject)
                            if subject and chapter_path else []),
        "selected": {"board": board, "class_level": class_level, "subject": subject,
                     "chapter": chapter},
        "show_chapter_filter": bool(chapter_path),
    }
    return queryset, context


def paginate(request, queryset, per_page=12):
    paginator = Paginator(queryset, per_page)
    page = request.GET.get("page")
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)
