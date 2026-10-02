from django.db.models import F
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from analytics.models import UserActivity
from analytics.services import log_activity
from core.files import serve_file
from core.filters import apply_hierarchy_filters, paginate, to_int
from questions.services.frequency import important_questions_for_paper

from .models import QuestionPaper

SORTS = {"newest": ("-year", "-created_at"), "oldest": ("year", "created_at"),
         "popular": ("-download_count",), "title": ("title",)}


def _filtered_papers(request, base_qs):
    qs, filter_ctx = apply_hierarchy_filters(request, base_qs.select_related(
        "subject__class_level__board", "chapter"))
    year = to_int(request.GET.get("year"))
    paper_type = request.GET.get("paper_type")
    exam_type = request.GET.get("exam_type")
    difficulty = request.GET.get("difficulty")
    q = request.GET.get("q", "").strip()
    if year:
        qs = qs.filter(year=year)
    if paper_type in QuestionPaper.PaperType.values:
        qs = qs.filter(paper_type=paper_type)
    if exam_type in QuestionPaper.ExamType.values:
        qs = qs.filter(exam_type=exam_type)
    if difficulty in QuestionPaper.Difficulty.values:
        qs = qs.filter(difficulty=difficulty)
    if q:
        qs = qs.filter(title__icontains=q)
    sort = request.GET.get("sort", "newest")
    qs = qs.order_by(*SORTS.get(sort, SORTS["newest"]))
    years = (base_qs.exclude(year__isnull=True).order_by("-year")
             .values_list("year", flat=True).distinct())
    return qs, {**filter_ctx, "years": years, "q": q, "sort": sort,
                "paper_types": QuestionPaper.PaperType.choices,
                "exam_types": QuestionPaper.ExamType.choices,
                "difficulties": QuestionPaper.Difficulty.choices}


def paper_list(request):
    qs, ctx = _filtered_papers(request, QuestionPaper.objects.published())
    return render(request, "papers/paper_list.html", {
        **ctx, "page_obj": paginate(request, qs, 12), "section": "papers",
        "heading": "Question Papers",
        "subheading": "Sample, model, practice, chapter-wise and pre-board papers for every board.",
    })


def previous_year_list(request):
    qs, ctx = _filtered_papers(
        request, QuestionPaper.objects.published().filter(paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR))
    return render(request, "papers/paper_list.html", {
        **ctx, "page_obj": paginate(request, qs, 12), "section": "previous_year",
        "heading": "Previous Year Papers",
        "subheading": "Real board examination papers from past years, with important questions "
                      "and historical frequency analysis.",
    })


def paper_detail(request, slug):
    paper = get_object_or_404(
        QuestionPaper.objects.published().select_related("subject__class_level__board", "chapter"),
        slug=slug)
    QuestionPaper.objects.filter(pk=paper.pk).update(view_count=F("view_count") + 1)
    log_activity(request.user, UserActivity.Type.VIEW_PAPER, f"Viewed {paper.title}", obj=paper)
    related = (QuestionPaper.objects.published().filter(subject=paper.subject)
               .exclude(pk=paper.pk).order_by("-year")[:4])
    return render(request, "papers/paper_detail.html", {
        "paper": paper,
        "related_papers": related,
        "important_questions": important_questions_for_paper(paper, limit=8),
        "related_tests": paper.tests.published()[:3],
    })


def paper_viewer(request, slug):
    """Full-screen PDF viewer page."""
    paper = get_object_or_404(QuestionPaper.objects.published(), slug=slug)
    return render(request, "papers/paper_viewer.html", {"paper": paper})


@xframe_options_sameorigin
def paper_file(request, slug):
    """Inline PDF bytes for the in-browser viewer."""
    paper = get_object_or_404(QuestionPaper.objects.published(), slug=slug)
    return serve_file(paper.pdf, paper.title, as_attachment=False)


def paper_download(request, slug):
    paper = get_object_or_404(QuestionPaper.objects.published(), slug=slug)
    QuestionPaper.objects.filter(pk=paper.pk).update(download_count=F("download_count") + 1)
    log_activity(request.user, UserActivity.Type.DOWNLOAD_PAPER, f"Downloaded {paper.title}",
                 obj=paper)
    field = paper.solution_pdf if request.GET.get("solutions") == "1" else paper.pdf
    return serve_file(field, paper.title, as_attachment=True)
