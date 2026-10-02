from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from analytics import services as analytics
from analytics.models import UserActivity
from assistant.models import AIConversation
from bookmarks.models import Bookmark
from bookmarks.services import content_type_for_kind
from recommendations.models import Recommendation
from recommendations.services import get_for_user
from scanner.models import ScannerHistory
from testengine.models import TestAttempt


def _chart_rows(rows, label_key):
    return [{"label": r[label_key], "accuracy": r["accuracy"], "score": r["score_pct"],
             "attempted": r["attempted"] or 0, "correct": r["correct"] or 0,
             "incorrect": r["incorrect"] or 0, "skipped": r["skipped"] or 0}
            for r in rows]


@login_required
def home(request):
    user = request.user
    weak, strong = analytics.weak_and_strong_areas(user)
    subject_rows = analytics.subject_performance(user)
    recs = get_for_user(user, limit=12)
    return render(request, "dashboard/home.html", {
        "summary": analytics.summary(user),
        "profile": user.profile,
        "active_attempts": TestAttempt.objects.filter(
            user=user, status=TestAttempt.Status.IN_PROGRESS).select_related("test")[:3],
        "recent_attempts": TestAttempt.objects.filter(user=user).exclude(
            status=TestAttempt.Status.IN_PROGRESS).select_related("test")[:5],
        "recent_activity": UserActivity.objects.filter(user=user)[:8],
        "bookmarked_papers": (Bookmark.objects.filter(user=user,
                                                      content_type=content_type_for_kind("paper"))
                              .prefetch_related("content_object")[:5]),
        "scans": ScannerHistory.objects.filter(user=user)[:4],
        "conversations": AIConversation.objects.filter(user=user, is_archived=False)[:4],
        "recommended_tests": [r for r in recs if r.rec_type == Recommendation.Type.TEST][:3],
        "recommended_materials": [r for r in recs if r.rec_type in (
            Recommendation.Type.MATERIAL, Recommendation.Type.REVISION)][:3],
        "other_recommendations": [r for r in recs if r.rec_type not in (
            Recommendation.Type.TEST, Recommendation.Type.MATERIAL, Recommendation.Type.REVISION)][:4],
        "subject_performance": _chart_rows(subject_rows, "subject__name"),
        "chapter_performance": analytics.chapter_performance(user)[:8],
        "weak_areas": weak[:5],
        "strong_areas": strong[:5],
    })


@login_required
def performance(request):
    user = request.user
    weak, strong = analytics.weak_and_strong_areas(user)
    chapter_rows = analytics.chapter_performance(user)
    return render(request, "dashboard/analytics.html", {
        "summary": analytics.summary(user),
        "subject_chart": _chart_rows(analytics.subject_performance(user), "subject__name"),
        "test_type_chart": _chart_rows(analytics.test_type_performance(user), "label"),
        "trend": analytics.score_trend(user, limit=30),
        "chapter_rows": chapter_rows,
        "weak_areas": weak,
        "strong_areas": strong,
    })
