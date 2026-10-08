"""
Global search across boards, classes, subjects, chapters, topics, questions,
papers, previous-year papers, tests and study materials.

Matching: every search term must appear in at least one of the category's
fields (AND of ORs, case-insensitive). This works on PostgreSQL;
for very large catalogues swap `_text_filter` for PostgreSQL full-text
search (SearchVector/SearchRank) or an external engine — callers are unaffected.
"""
from django.core.cache import cache
from django.db.models import Count, Q

from boards.models import Board, Chapter, ClassLevel, Subject, Topic
from content.models import StudyMaterial
from core.utils import normalize_text
from papers.models import QuestionPaper
from questions.models import Question
from testengine.models import Test

from .models import SearchHistory

MAX_TERMS = 8
POPULAR_MIN_USERS = 3  # distinct users before a query is offered as a suggestion


def _text_filter(fields, query):
    terms = [t for t in query.split() if t][:MAX_TERMS]
    condition = Q()
    for term in terms:
        any_field = Q()
        for field in fields:
            any_field |= Q(**{f"{field}__icontains": term})
        condition &= any_field
    return condition


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Category:
    """Describes how one content type is searched, filtered and displayed."""

    def __init__(self, key, label, icon, queryset, fields, paths, to_item):
        self.key, self.label, self.icon = key, label, icon
        self._queryset, self.fields, self.paths, self.to_item = queryset, fields, paths, to_item

    def search(self, query, filters):
        qs = self._queryset()
        if query:
            qs = qs.filter(_text_filter(self.fields, query))
        for name, path in self.paths.items():
            value = filters.get(name)
            if value and path:
                qs = qs.filter(**{path: value})
            elif value and path is None:
                return qs.none()  # filter not applicable to this category
        return qs


def _subject_line(subject):
    return f"{subject.class_level.board} · {subject.class_level.name} · {subject.name}"


CATEGORIES = [
    Category(
        "boards", "Boards", "bank",
        lambda: Board.objects.published(),
        ["name", "short_name", "state"],
        {"board": "id", "class_level": None, "subject": None, "chapter": None, "year": None},
        lambda o: {"title": o.name, "subtitle": o.get_board_type_display(), "url": o.get_absolute_url()},
    ),
    Category(
        "classes", "Classes", "mortarboard",
        lambda: ClassLevel.objects.published().select_related("board"),
        ["name", "board__name", "board__short_name"],
        {"board": "board_id", "class_level": "id", "subject": None, "chapter": None, "year": None},
        lambda o: {"title": o.name, "subtitle": o.board.name, "url": o.get_absolute_url()},
    ),
    Category(
        "subjects", "Subjects", "book",
        lambda: Subject.objects.published().select_related("class_level__board"),
        ["name", "code", "description"],
        {"board": "class_level__board_id", "class_level": "class_level_id", "subject": "id",
         "chapter": None, "year": None},
        lambda o: {"title": o.name, "subtitle": f"{o.class_level.board} · {o.class_level.name}",
                   "url": o.get_absolute_url()},
    ),
    Category(
        "chapters", "Chapters", "bookmark",
        lambda: Chapter.objects.published().select_related("subject__class_level__board"),
        ["name", "description"],
        {"board": "subject__class_level__board_id", "class_level": "subject__class_level_id",
         "subject": "subject_id", "chapter": "id", "year": None},
        lambda o: {"title": o.name, "subtitle": _subject_line(o.subject), "url": o.get_absolute_url()},
    ),
    Category(
        "topics", "Topics", "diagram-3",
        lambda: Topic.objects.published().select_related("chapter__subject__class_level__board"),
        ["name", "description"],
        {"board": "chapter__subject__class_level__board_id",
         "class_level": "chapter__subject__class_level_id", "subject": "chapter__subject_id",
         "chapter": "chapter_id", "year": None},
        lambda o: {"title": o.name, "subtitle": f"{o.chapter.name} · {o.chapter.subject.name}",
                   "url": o.get_absolute_url()},
    ),
    Category(
        "questions", "Questions", "question-circle",
        lambda: Question.objects.published().select_related("subject__class_level__board", "chapter"),
        ["text", "answer", "concepts__name"],
        {"board": "subject__class_level__board_id", "class_level": "subject__class_level_id",
         "subject": "subject_id", "chapter": "chapter_id", "year": "appearances__year"},
        lambda o: {"title": o.text[:140], "subtitle": _subject_line(o.subject),
                   "url": o.get_absolute_url(), "badge": o.get_difficulty_display()},
    ),
    Category(
        "papers", "Question papers", "file-earmark-text",
        lambda: QuestionPaper.objects.published().exclude(paper_type="previous_year")
        .select_related("subject__class_level__board"),
        ["title", "description", "subject__name"],
        {"board": "subject__class_level__board_id", "class_level": "subject__class_level_id",
         "subject": "subject_id", "chapter": "chapter_id", "year": "year"},
        lambda o: {"title": o.title, "subtitle": _subject_line(o.subject),
                   "url": o.get_absolute_url(), "badge": o.get_paper_type_display()},
    ),
    Category(
        "previous_year", "Previous year papers", "clock-history",
        lambda: QuestionPaper.objects.published().filter(paper_type="previous_year")
        .select_related("subject__class_level__board"),
        ["title", "description", "subject__name"],
        {"board": "subject__class_level__board_id", "class_level": "subject__class_level_id",
         "subject": "subject_id", "chapter": "chapter_id", "year": "year"},
        lambda o: {"title": o.title, "subtitle": _subject_line(o.subject),
                   "url": o.get_absolute_url(), "badge": str(o.year or "")},
    ),
    Category(
        "tests", "Tests", "clipboard-check",
        lambda: Test.objects.published().select_related("board", "class_level", "subject"),
        ["title", "description", "subject__name", "chapter__name"],
        {"board": "board_id", "class_level": "class_level_id", "subject": "subject_id",
         "chapter": "chapter_id", "year": "paper__year"},
        lambda o: {"title": o.title, "subtitle": o.get_test_type_display(),
                   "url": o.get_absolute_url(), "badge": f"{o.duration_minutes} min"},
    ),
    Category(
        "materials", "Study material", "journal-text",
        lambda: StudyMaterial.objects.published().select_related("subject__class_level__board"),
        ["title", "summary", "body", "chapter__name", "topic__name"],
        {"board": "subject__class_level__board_id", "class_level": "subject__class_level_id",
         "subject": "subject_id", "chapter": "chapter_id", "year": None},
        lambda o: {"title": o.title, "subtitle": _subject_line(o.subject),
                   "url": o.get_absolute_url(), "badge": o.get_material_type_display()},
    ),
]
CATEGORY_MAP = {c.key: c for c in CATEGORIES}


def clean_filters(params):
    return {
        "board": _int(params.get("board")),
        "class_level": _int(params.get("class_level")),
        "subject": _int(params.get("subject")),
        "chapter": _int(params.get("chapter")),
        "year": _int(params.get("year")),
        "type": params.get("type") if params.get("type") in CATEGORY_MAP else None,
    }


def search(query, filters, per_category=5):
    """Return grouped results: [{key, label, icon, count, items}] (non-empty groups only)."""
    query = (query or "").strip()[:200]
    if not query and not any(v for k, v in filters.items() if k != "type"):
        return []
    categories = [CATEGORY_MAP[filters["type"]]] if filters.get("type") else CATEGORIES
    groups = []
    for category in categories:
        qs = category.search(query, filters).distinct()
        items = [dict(category.to_item(obj), type=category.key) for obj in qs[:per_category]]
        if items:
            groups.append({"key": category.key, "label": category.label, "icon": category.icon,
                           "count": qs.count() if len(items) == per_category else len(items),
                           "items": items})
    return groups


def search_category_queryset(key, query, filters):
    """Full queryset for one category (used by paginated 'see all' views)."""
    return CATEGORY_MAP[key].search((query or "").strip()[:200], filters).distinct()


def record_search(user, query, filters, results_count):
    query = (query or "").strip()
    if not query:
        return
    normalized = normalize_text(query)[:255]
    if user is not None and user.is_authenticated:
        last = SearchHistory.objects.filter(user=user).first()
        if last and last.normalized_query == normalized:
            return
    SearchHistory.objects.create(
        user=user if user is not None and user.is_authenticated else None,
        query=query[:255], normalized_query=normalized,
        filters={k: v for k, v in filters.items() if v}, results_count=results_count,
    )


def recent_searches(user, limit=8):
    if user is None or not user.is_authenticated:
        return []
    seen, result = set(), []
    for item in SearchHistory.objects.filter(user=user).only("query", "normalized_query")[:50]:
        if item.normalized_query not in seen:
            seen.add(item.normalized_query)
            result.append(item.query)
        if len(result) >= limit:
            break
    return result


def suggestions(prefix, limit=8):
    """Autocomplete suggestions from the catalogue plus popular searches (cached)."""
    prefix = (prefix or "").strip()
    if len(prefix) < 2:
        return []
    cache_key = f"search_suggest:{normalize_text(prefix)[:50]}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    results = []

    def add(text, kind, url=""):
        if text and all(r["text"].lower() != text.lower() for r in results):
            results.append({"text": text, "type": kind, "url": url})

    for s in Subject.objects.published().filter(name__icontains=prefix).select_related(
            "class_level__board")[:3]:
        add(f"{s.name} — {s.class_level.board} {s.class_level.name}", "subject", s.get_absolute_url())
    for c in Chapter.objects.published().filter(name__icontains=prefix).select_related(
            "subject__class_level__board")[:3]:
        add(c.name, "chapter", c.get_absolute_url())
    for t in Topic.objects.published().filter(name__icontains=prefix).select_related(
            "chapter__subject__class_level__board")[:2]:
        add(t.name, "topic", t.get_absolute_url())
    for p in QuestionPaper.objects.published().filter(title__icontains=prefix)[:2]:
        add(p.title, "paper", p.get_absolute_url())
    # Only suggest searches made by several different people, so one user's private queries
    # are never shown to everyone (and a single user can't plant suggestions).
    popular = (SearchHistory.objects.filter(normalized_query__startswith=normalize_text(prefix))
               .values("query").annotate(n=Count("user", distinct=True))
               .filter(n__gte=POPULAR_MIN_USERS).order_by("-n")[:3])
    for row in popular:
        add(row["query"], "popular")

    results = results[:limit]
    cache.set(cache_key, results, 300)
    return results
