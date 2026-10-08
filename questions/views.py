from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from analytics.models import UserActivity
from analytics.services import log_activity
from boards.models import Subject
from core.filters import apply_hierarchy_filters, paginate, to_int
from testengine.services import locked_question_ids

from .models import Question
from .services.frequency import DISCLAIMER, analyze_question, subject_overview
from .services.predictor import predict, predict_for_question


def question_list(request):
    qs = (Question.objects.published()
          .select_related("subject__class_level__board", "chapter")
          .annotate(appearance_years=Count("appearances__year", distinct=True)))
    qs, filter_ctx = apply_hierarchy_filters(request, qs)
    difficulty = request.GET.get("difficulty")
    qtype = request.GET.get("type")
    if difficulty in Question.Difficulty.values:
        qs = qs.filter(difficulty=difficulty)
    if qtype in Question.Type.values:
        qs = qs.filter(question_type=qtype)
    if request.GET.get("asked") == "1":
        qs = qs.filter(appearance_years__gt=0)
    if request.GET.get("important") == "1":
        qs = qs.filter(is_important=True)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(text__icontains=q)
    page = paginate(request, qs.order_by("-is_important", "-appearance_years", "-created_at"), 15)
    return render(request, "questions/question_list.html", {
        "page_obj": page, **filter_ctx, "q": q,
        "difficulties": Question.Difficulty.choices, "types": Question.Type.choices,
    })


def question_detail(request, pk):
    question = get_object_or_404(
        Question.objects.published().select_related("subject__class_level__board", "chapter", "topic")
        .prefetch_related("options", "concepts"),
        pk=pk,
    )
    log_activity(request.user, UserActivity.Type.VIEW_QUESTION, question.text[:80], obj=question)
    return render(request, "questions/question_detail.html", {
        "question": question,
        "answers_locked": question.pk in locked_question_ids(request.user),
        "analysis": analyze_question(question),
        "prediction": predict_for_question(question),
    })


def predictor(request):
    """Exam Question Predictor: paste any question → history + likelihood estimate."""
    params = request.GET.copy()
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    # Default the scope to the student's own board/class the first time they open the page.
    if profile and not any(params.get(k) for k in ("board", "class_level", "subject", "q")):
        if profile.board_id:
            params["board"] = profile.board_id
        if profile.class_level_id:
            params["class_level"] = profile.class_level_id
    request.GET = params
    _unused, filter_ctx = apply_hierarchy_filters(request, Question.objects.none(), chapter_path=None)
    text = params.get("q", "").strip()[:2000]
    report = None
    if text:
        selected = filter_ctx["selected"]
        report = predict(text, board=selected["board"], class_level=selected["class_level"],
                         subject=selected["subject"])
    ai_prompt = ""
    if report and report["has_matches"]:
        ai_prompt = (f"This question appeared {report['times_appeared']} time(s) in previous board papers "
                     f"({', '.join(map(str, report['years']))}). Explain it step by step and give me 3 similar "
                     f"practice questions: {text}")[:1000]
    return render(request, "questions/predictor.html", {
        **filter_ctx, "q": text, "report": report, "disclaimer": DISCLAIMER, "ai_prompt": ai_prompt,
        "examples": ["Explain Newton's laws of motion.",
                     "The sum of the squares of two consecutive positive integers is 365. Find them.",
                     "What is photosynthesis? Write its balanced chemical equation.",
                     "Find the discriminant of 3x² − 2x + 1/3 = 0"],
    })


def frequency_overview(request):
    """Subject-level 'Question Prediction & Frequency Analysis' page."""
    # Only the filter-bar context is needed here; the queryset itself is unused.
    _unused, filter_ctx = apply_hierarchy_filters(request, Question.objects.none(), chapter_path=None)
    subject = None
    subject_id = to_int(request.GET.get("subject"))
    if subject_id:
        subject = get_object_or_404(Subject.objects.published().select_related("class_level__board"),
                                    pk=subject_id)
    return render(request, "questions/frequency_overview.html", {
        **filter_ctx,
        "subject": subject,
        "overview": subject_overview(subject) if subject else None,
        "disclaimer": DISCLAIMER,
    })
