from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from analytics.models import UserActivity
from boards.models import Board, Chapter, ClassLevel, Subject
from analytics.services import log_activity
from core.files import serve_file
from core.filters import apply_hierarchy_filters, paginate, to_int
from questions.services.frequency import important_questions_for_paper

from .models import QuestionPaper
from .services import chapter_questions, recent_exam_years, year_grid

SORTS = {"newest": ("-year", "-created_at"), "oldest": ("year", "created_at"),
         "popular": ("-download_count",), "title": ("title",)}


def _filtered_papers(request, base_qs):
    qs, filter_ctx = apply_hierarchy_filters(request, base_qs.select_related(
        "subject__class_level__board", "chapter"), chapter_path=None)
    # Full board papers aren't tied to one chapter: match chapter-wise papers and papers
    # with questions recorded from the chapter.
    chapter = to_int(request.GET.get("chapter"))
    subject = filter_ctx["selected"]["subject"]
    if chapter and subject:
        qs = qs.filter(Q(chapter_id=chapter) | Q(appearances__question__chapter_id=chapter)).distinct()
    filter_ctx.update(show_chapter_filter=True, selected={**filter_ctx["selected"], "chapter": chapter},
                      filter_chapters=Chapter.objects.published().filter(subject_id=subject) if subject else [])
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


def _pick(objects, value):
    """Find an object by id or slug from a query-string value."""
    value = (value or "").strip()
    return next((o for o in objects if value and value in (str(o.pk), getattr(o, "slug", None))), None)


def previous_year_archive(request):
    """
    Previous-year papers for the last five years as a subject × year grid, filtered by
    board → class → subject → chapter, year and exam type.
    """
    params = request.GET
    all_years = recent_exam_years()
    year = to_int(params.get("year"))
    years = [year] if year in all_years else all_years
    exam_type = params.get("exam_type")
    exam_type = exam_type if exam_type in QuestionPaper.ExamType.values else None

    pyp = Q(classes__subjects__papers__paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR,
            classes__subjects__papers__is_published=True,
            classes__subjects__papers__year__in=all_years)
    boards = list(Board.objects.published()
                  .annotate(paper_count=Count("classes__subjects__papers", filter=pyp, distinct=True)))
    board = _pick(boards, params.get("board"))
    if board is None and boards:
        board = next((b for b in boards if b.paper_count), boards[0])

    classes, class_level, subjects, subject, chapters, chapter = [], None, [], None, [], None
    if board:
        classes = list(ClassLevel.objects.published().filter(board=board).order_by("-number"))
        class_level = _pick(classes, params.get("class_level") or params.get("class"))
        if class_level is None and classes:
            class_level = next((c for c in classes if c.number == 10), classes[0])
    if class_level:
        subjects = list(Subject.objects.published().filter(class_level=class_level)
                        .select_related("class_level__board"))
        subject = _pick(subjects, params.get("subject"))
    if subject:
        chapters = list(Chapter.objects.published().filter(subject=subject))
        chapter = _pick(chapters, params.get("chapter"))

    rows = year_grid([subject] if subject else subjects, years, exam_type) if class_level else []
    model_papers = (QuestionPaper.objects.published()
                    .filter(paper_type=QuestionPaper.PaperType.MODEL, subject__class_level=class_level)
                    .count() if class_level else 0)
    return render(request, "papers/previous_year_archive.html", {
        "section": "previous_year", "years": years, "all_years": all_years,
        "boards": boards, "board": board, "classes": classes, "class_level": class_level,
        "subjects": subjects, "subject": subject, "chapters": chapters, "chapter": chapter,
        "year": year if year in all_years else None, "exam_type": exam_type,
        "exam_types": QuestionPaper.ExamType.choices,
        "chapter_questions": chapter_questions(chapter, years, exam_type) if chapter else None,
        "rows": rows, "model_papers": model_papers,
        "available": sum(r["available"] for r in rows),
        "possible": len(rows) * len(years),
        "is_filtered": bool(subject or year in all_years or exam_type),
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
