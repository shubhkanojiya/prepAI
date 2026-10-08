import logging

from django.core.cache import cache
from django.db.models import Count
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from boards.models import Board, Subject
from content.models import StudyMaterial
from papers.models import QuestionPaper
from papers.services import recent_exam_years
from questions.models import Question
from services.ai_service import is_configured as ai_is_configured
from testengine.models import Test

logger = logging.getLogger("prepai")

FAQS = [
    ("Which boards does PrepAI support?",
     "PrepAI supports CBSE, ICSE and state boards. New boards, classes and subjects are added "
     "regularly by our content team."),
    ("How does the AI Scanner work?",
     "Take a photo of a printed or handwritten question (or upload one). PrepAI reads it, "
     "identifies the subject and topic, and gives an answer with step-by-step explanation, "
     "the underlying concept and follow-up practice questions."),
    ("Can PrepAI predict exam questions?",
     "No one can know exactly what will appear in an exam. PrepAI's Frequency Analysis shows how "
     "often a question or concept appeared in stored previous-year papers, so you can prioritise "
     "revision. Historical analysis does not guarantee appearance in a future examination."),
    ("Are the tests timed like real exams?",
     "Yes. Tests have a timer, question palette, mark-for-review and auto-submit when time runs "
     "out. Your answers are saved as you go."),
    ("Is my data private?",
     "Your scans, AI conversations and results are visible only to you. We never show your "
     "personal data to other students."),
    ("Do I need an account?",
     "You can browse papers and study material freely. Create a free account to take tests, "
     "save bookmarks, track progress and use the AI assistant."),
]


# Subjects the hero prefers to show as examples, in order.
SHOWCASE_SUBJECTS = ["Science", "Mathematics", "Physics", "Chemistry", "Biology", "Social Science"]


def _hero_data():
    """Live numbers for the homepage hero: real previous-year papers in the last five exam years."""
    years = recent_exam_years()
    pyp = (QuestionPaper.objects.published()
           .filter(paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR, is_sample=False, year__in=years))
    level = "subject__class_level"
    rows = (pyp.values(f"{level}__board__slug", f"{level}__board__short_name", f"{level}__board__order",
                       f"{level}__board__state",
                       f"{level}__slug", f"{level}__name", f"{level}__number")
            .annotate(n=Count("id"))
            .order_by(f"{level}__board__order", f"{level}__number"))
    finder = {}
    for r in rows:
        short, state = r[f"{level}__board__short_name"], r[f"{level}__board__state"]
        board = finder.setdefault(r[f"{level}__board__slug"], {
            "slug": r[f"{level}__board__slug"], "name": f"{state} ({short})" if state else short,
            "classes": []})
        board["classes"].append({"slug": r[f"{level}__slug"], "name": r[f"{level}__name"], "count": r["n"]})

    showcase = []
    subject_rows = (pyp.values(f"{level}__board__short_name", f"{level}__board__order", f"{level}__name",
                               "subject__name").annotate(n=Count("id")))
    by_board = {}
    for r in subject_rows:
        by_board.setdefault(r[f"{level}__board__short_name"], []).append(r)
    for board, items in sorted(by_board.items(), key=lambda kv: kv[1][0][f"{level}__board__order"]):
        rank = {name: i for i, name in enumerate(SHOWCASE_SUBJECTS)}
        best = min(items, key=lambda r: (rank.get(r["subject__name"], 99), -r["n"]))
        showcase.append({"board": board, "class": best[f"{level}__name"], "subject": best["subject__name"],
                         "count": best["n"]})

    present_years = sorted(set(pyp.values_list("year", flat=True)), reverse=True)
    return {
        "papers": pyp.count(),
        "subjects": pyp.values("subject").distinct().count(),
        "boards": len(finder),
        "years": years,
        "latest_year": present_years[0] if present_years else None,
        "finder": list(finder.values()),
        "showcase": showcase,
    }


def home(request):
    stats = cache.get("home_stats")
    if stats is None:
        stats = {
            "boards": Board.objects.published().count(),
            "papers": QuestionPaper.objects.published().count(),
            "questions": Question.objects.published().count(),
            "tests": Test.objects.published().count(),
        }
        cache.set("home_stats", stats, 600)
    hero = cache.get("home_hero")
    if hero is None:
        hero = _hero_data()
        cache.set("home_hero", hero, 600)

    context = {
        "stats": stats,
        "hero": hero,
        "popular_boards": Board.objects.published().filter(is_featured=True)[:8]
        or Board.objects.published()[:8],
        "popular_subjects": (Subject.objects.published().filter(is_popular=True)
                             .select_related("class_level__board")[:8]),
        "faqs": FAQS,
        "ai_enabled": ai_is_configured(),
    }
    if request.user.is_authenticated:
        from recommendations.services import get_for_user

        context["recommendations"] = get_for_user(request.user, limit=6)
    else:
        context["latest_materials"] = (StudyMaterial.objects.published()
                                       .select_related("subject__class_level__board")
                                       .order_by("-is_featured", "-created_at")[:3])
        context["latest_papers"] = (QuestionPaper.objects.published()
                                    .select_related("subject__class_level__board")
                                    .order_by("-year", "-created_at")[:3])
    return render(request, "core/home.html", context)


ROBOTS_TXT = """User-agent: *
Disallow: /admin/
Disallow: /api/
Disallow: /accounts/
Disallow: /dashboard/
Disallow: /saved/
Disallow: /notifications/
Disallow: /assistant/
Disallow: /tests/attempt/
Disallow: /search/
"""


def robots_txt(request):
    """Let crawlers index public study content but not personal or API pages."""
    return HttpResponse(ROBOTS_TXT, content_type="text/plain")


@never_cache
def healthz(request):
    """Liveness/readiness probe for load balancers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        logger.exception("Health check: database unavailable")
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok},
                        status=200 if db_ok else 503)


def _wants_json(request):
    return request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", "")


def _error(request, status, title, message, icon):
    if _wants_json(request):
        return JsonResponse({"error": {"message": message, "code": status}}, status=status)
    try:
        return render(request, "errors/error.html",
                      {"status": status, "title": title, "message": message, "icon": icon},
                      status=status)
    except Exception:
        # Rendering can fail when the failure is systemic (e.g. database down).
        logger.exception("Error page rendering failed")
        return HttpResponse(
            f"<!doctype html><title>{title}</title><h1>{title}</h1><p>{message}</p>",
            status=status)


def error_400(request, exception=None):
    return _error(request, 400, "Bad request",
                  "Something about that request didn't look right. Please try again.",
                  "exclamation-octagon")


def error_403(request, exception=None):
    return _error(request, 403, "Access denied",
                  "You don't have permission to view this page. Try signing in with a "
                  "different account.", "shield-lock")


def error_404(request, exception=None):
    return _error(request, 404, "Page not found",
                  "We couldn't find what you were looking for. It may have been moved or "
                  "unpublished.", "compass")


def error_500(request):
    return _error(request, 500, "Something went wrong",
                  "An unexpected error occurred on our side. Our team has been notified — "
                  "please try again in a moment.", "tools")


def csrf_failure(request, reason=""):
    return _error(request, 403, "Session expired",
                  "Your session expired or the form was submitted twice. Refresh the page "
                  "and try again.", "arrow-clockwise")
