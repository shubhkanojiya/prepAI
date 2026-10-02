"""Activity logging and performance analytics."""
import logging
from collections import defaultdict
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count, Max, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import PerformanceRecord, UserActivity

logger = logging.getLogger("prepai.analytics")


def log_activity(user, activity_type, description="", obj=None, url="", **metadata):
    """Best-effort activity logging — never breaks the calling request."""
    if user is None or not user.is_authenticated:
        return None
    try:
        return UserActivity.objects.create(
            user=user,
            activity_type=activity_type,
            description=description[:255],
            content_type=ContentType.objects.get_for_model(obj) if obj is not None else None,
            object_id=obj.pk if obj is not None else None,
            url=(url or (obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else ""))[:300],
            metadata=metadata,
        )
    except Exception:
        logger.exception("Failed to log activity")
        return None


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------
def record_attempt_performance(attempt):
    """Create one PerformanceRecord per (subject, chapter) touched by the attempt."""
    PerformanceRecord.objects.filter(attempt=attempt).delete()
    buckets = defaultdict(lambda: {"total": 0, "attempted": 0, "correct": 0, "incorrect": 0,
                                   "skipped": 0, "score": 0, "max": 0, "time": 0})
    answers = attempt.answers.select_related("test_question__question")
    for answer in answers:
        question = answer.test_question.question
        if not question.is_auto_graded:
            continue
        b = buckets[(question.subject_id, question.chapter_id)]
        b["total"] += 1
        b["max"] += answer.test_question.effective_marks
        b["score"] += answer.marks_awarded
        b["time"] += answer.time_spent_seconds
        if answer.is_correct is None:
            b["skipped"] += 1
        else:
            b["attempted"] += 1
            b["correct" if answer.is_correct else "incorrect"] += 1

    records = [
        PerformanceRecord(
            user=attempt.user, attempt=attempt, subject_id=subject_id, chapter_id=chapter_id,
            test_type=attempt.test.test_type, total_questions=b["total"],
            attempted=b["attempted"], correct=b["correct"], incorrect=b["incorrect"],
            skipped=b["skipped"], score=b["score"], max_score=b["max"], time_seconds=b["time"],
            recorded_on=timezone.localdate(attempt.submitted_at or timezone.now()),
        )
        for (subject_id, chapter_id), b in buckets.items()
    ]
    PerformanceRecord.objects.bulk_create(records)
    return records


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _pct(part, whole):
    return round(100.0 * float(part) / float(whole), 1) if whole else 0.0


def _aggregate(queryset, group_fields):
    rows = (
        queryset.values(*group_fields)
        .annotate(attempted=Sum("attempted"), correct=Sum("correct"),
                  incorrect=Sum("incorrect"), skipped=Sum("skipped"),
                  total=Sum("total_questions"), score=Sum("score"), max_score=Sum("max_score"),
                  time=Sum("time_seconds"), tests=Count("attempt", distinct=True))
    )
    result = []
    for row in rows:
        row["accuracy"] = _pct(row["correct"], row["attempted"])
        row["score_pct"] = _pct(max(row["score"] or 0, 0), row["max_score"])
        result.append(row)
    return result


def subject_performance(user):
    rows = _aggregate(PerformanceRecord.objects.filter(user=user),
                      ["subject_id", "subject__name", "subject__class_level__name"])
    return sorted(rows, key=lambda r: r["subject__name"])


def chapter_performance(user, subject=None):
    qs = PerformanceRecord.objects.filter(user=user, chapter__isnull=False)
    if subject is not None:
        qs = qs.filter(subject=subject)
    rows = _aggregate(qs, ["chapter_id", "chapter__name", "subject__name"])
    return sorted(rows, key=lambda r: (r["subject__name"], r["chapter__name"]))


def test_type_performance(user):
    from testengine.models import Test

    labels = dict(Test.TestType.choices)
    rows = _aggregate(PerformanceRecord.objects.filter(user=user), ["test_type"])
    for row in rows:
        row["label"] = labels.get(row["test_type"], row["test_type"])
    return rows


def score_trend(user, limit=20):
    from testengine.models import TestAttempt

    attempts = (
        TestAttempt.objects.filter(user=user).exclude(status=TestAttempt.Status.IN_PROGRESS)
        .select_related("test").order_by("-submitted_at")[:limit]
    )
    return [
        {"date": timezone.localtime(a.submitted_at).strftime("%d %b"),
         "title": a.test.title, "percentage": round(a.percentage, 1),
         "accuracy": round(a.accuracy, 1)}
        for a in reversed(list(attempts))
    ]


def weak_and_strong_areas(user, min_attempted=3, weak_below=60, strong_from=80):
    chapters = [c for c in chapter_performance(user) if (c["attempted"] or 0) >= min_attempted]
    weak = sorted([c for c in chapters if c["accuracy"] < weak_below], key=lambda c: c["accuracy"])
    strong = sorted([c for c in chapters if c["accuracy"] >= strong_from],
                    key=lambda c: -c["accuracy"])
    return weak, strong


def study_streak(user):
    """Consecutive days (ending today or yesterday) with any recorded activity."""
    since = timezone.now() - timedelta(days=365)
    days = set(
        UserActivity.objects.filter(user=user, created_at__gte=since)
        .annotate(day=TruncDate("created_at")).values_list("day", flat=True)
    )
    today = timezone.localdate()
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def summary(user):
    from testengine.models import TestAnswer, TestAttempt

    finished = TestAttempt.objects.filter(user=user).exclude(status=TestAttempt.Status.IN_PROGRESS)
    stats = finished.aggregate(count=Count("id"), avg=Avg("percentage"), best=Max("percentage"))
    solved = TestAnswer.objects.filter(attempt__in=finished, is_correct__isnull=False).count()
    return {
        "tests_attempted": stats["count"] or 0,
        "average_score": round(stats["avg"] or 0, 1),
        "best_score": round(stats["best"] or 0, 1),
        "questions_solved": solved,
        "study_streak": study_streak(user),
    }
