from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.filters import apply_hierarchy_filters, paginate

from . import services
from .models import Test, TestAttempt
from .serializers import AttemptSerializer, attempt_question_payload


def _test_queryset():
    return (Test.objects.published().select_related("subject", "chapter", "class_level__board")
            .annotate(question_count=Count("test_questions",
                                           filter=Q(test_questions__question__is_published=True))))


def test_list(request, mock=False):
    qs = _test_queryset()
    if mock:
        qs = qs.filter(test_type=Test.TestType.MOCK)
    else:
        qs = qs.exclude(test_type=Test.TestType.MOCK)
    qs, filter_ctx = apply_hierarchy_filters(request, qs)
    test_type = request.GET.get("test_type")
    difficulty = request.GET.get("difficulty")
    if test_type in Test.TestType.values and not mock:
        qs = qs.filter(test_type=test_type)
    if difficulty in Test.Difficulty.values:
        qs = qs.filter(difficulty=difficulty)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(title__icontains=q)

    attempted = {}
    if request.user.is_authenticated:
        for a in TestAttempt.objects.filter(user=request.user).exclude(
                status=TestAttempt.Status.IN_PROGRESS).order_by("test_id", "-percentage"):
            attempted.setdefault(a.test_id, a.percentage)
    return render(request, "testengine/test_list.html", {
        **filter_ctx,
        "page_obj": paginate(request, qs.order_by("-is_featured", "-created_at"), 12),
        "mock": mock,
        "test_types": [c for c in Test.TestType.choices if c[0] != Test.TestType.MOCK],
        "difficulties": Test.Difficulty.choices,
        "best_scores": attempted,
        "q": q,
    })


def test_detail(request, slug):
    test = get_object_or_404(_test_queryset(), slug=slug)
    context = {"test": test}
    if request.user.is_authenticated:
        attempts = TestAttempt.objects.filter(user=request.user, test=test)
        context["active_attempt"] = attempts.filter(status=TestAttempt.Status.IN_PROGRESS).first()
        context["past_attempts"] = attempts.exclude(status=TestAttempt.Status.IN_PROGRESS)[:5]
        context["attempts_left"] = (max(test.max_attempts - attempts.count(), 0)
                                    if test.max_attempts else None)
    return render(request, "testengine/test_detail.html", context)


@login_required
@require_POST
def start_test(request, slug):
    test = get_object_or_404(Test.objects.published(), slug=slug)
    try:
        attempt = services.start_attempt(request.user, test)
    except services.TestEngineError as exc:
        messages.error(request, str(exc))
        return redirect(test.get_absolute_url())
    return redirect("testengine:attempt", pk=attempt.pk)


@login_required
def attempt_view(request, pk):
    attempt = get_object_or_404(TestAttempt.objects.select_related("test"), pk=pk, user=request.user)
    attempt = services.expire_if_needed(attempt)
    if not attempt.is_in_progress:
        messages.info(request, "This test has been submitted. Here are your results.")
        return redirect("testengine:result", pk=attempt.pk)
    answers = {a.test_question_id: a for a in attempt.answers.prefetch_related("selected_options")}
    payload = {
        "attempt": AttemptSerializer(attempt).data,
        "questions": attempt_question_payload(attempt, services.ordered_test_questions(attempt),
                                              answers),
    }
    return render(request, "testengine/attempt.html", {"attempt": attempt, "payload": payload})


@login_required
@require_POST
def submit_view(request, pk):
    """Non-JS fallback submission."""
    attempt = get_object_or_404(TestAttempt, pk=pk, user=request.user)
    services.submit_attempt(attempt)
    return redirect("testengine:result", pk=attempt.pk)


@login_required
def result_view(request, pk):
    attempt = get_object_or_404(TestAttempt.objects.select_related("test", "test__subject",
                                                                   "test__chapter"),
                                pk=pk, user=request.user)
    attempt = services.expire_if_needed(attempt)
    if attempt.is_in_progress:
        return redirect("testengine:attempt", pk=attempt.pk)
    result = services.build_result(attempt)

    weak_chapters = [c["name"] for c in result["chapter_breakdown"] if c["score_pct"] < 60]
    from content.models import StudyMaterial

    recommended_materials = StudyMaterial.objects.published().filter(
        chapter__name__in=weak_chapters, subject__class_level=attempt.test.class_level)[:4]
    recommended_tests = (Test.objects.published()
                         .filter(Q(chapter__name__in=weak_chapters) | Q(subject=attempt.test.subject))
                         .exclude(pk=attempt.test_id).distinct()[:3])
    return render(request, "testengine/result.html", {
        "attempt": attempt,
        "test": attempt.test,
        **result,
        "weak_chapters": weak_chapters,
        "recommended_materials": recommended_materials,
        "recommended_tests": recommended_tests,
    })


@login_required
def history(request):
    attempts = (TestAttempt.objects.filter(user=request.user).select_related("test")
                .order_by("-started_at"))
    return render(request, "testengine/history.html", {"page_obj": paginate(request, attempts, 15)})
