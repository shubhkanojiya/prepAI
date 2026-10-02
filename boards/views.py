from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render

from analytics.models import UserActivity
from analytics.services import log_activity
from content.models import StudyMaterial
from papers.models import QuestionPaper
from questions.models import Question
from testengine.models import Test

from .models import Board, Chapter, ClassLevel, Subject, Topic


def board_list(request):
    boards = (Board.objects.published()
              .annotate(class_count=Count("classes", filter=Q(classes__is_published=True))))
    grouped = {
        "National boards": [b for b in boards if b.board_type != Board.BoardType.STATE],
        "State boards": [b for b in boards if b.board_type == Board.BoardType.STATE],
    }
    return render(request, "boards/board_list.html", {"grouped_boards": grouped})


def board_detail(request, board_slug):
    board = get_object_or_404(Board.objects.published(), slug=board_slug)
    classes = (board.classes.published()
               .annotate(subject_count=Count("subjects", filter=Q(subjects__is_published=True))))
    return render(request, "boards/board_detail.html", {"board": board, "classes": classes})


def _get_class(board_slug, class_slug):
    return get_object_or_404(ClassLevel.objects.published().select_related("board"),
                             board__slug=board_slug, board__is_published=True, slug=class_slug)


def class_detail(request, board_slug, class_slug):
    class_level = _get_class(board_slug, class_slug)
    subjects = (class_level.subjects.published()
                .annotate(chapter_count=Count("chapters", filter=Q(chapters__is_published=True),
                                              distinct=True),
                          paper_count=Count("papers", filter=Q(papers__is_published=True),
                                            distinct=True)))
    return render(request, "boards/class_detail.html",
                  {"board": class_level.board, "class_level": class_level, "subjects": subjects})


def _get_subject(board_slug, class_slug, subject_slug):
    class_level = _get_class(board_slug, class_slug)
    return get_object_or_404(class_level.subjects.published().select_related("class_level__board"),
                             slug=subject_slug)


def subject_detail(request, board_slug, class_slug, subject_slug):
    subject = _get_subject(board_slug, class_slug, subject_slug)
    chapters = (subject.chapters.published()
                .annotate(question_count=Count("questions", filter=Q(questions__is_published=True),
                                               distinct=True),
                          material_count=Count("materials", filter=Q(materials__is_published=True),
                                               distinct=True))
                .prefetch_related(Prefetch("topics", queryset=Topic.objects.published())))
    context = {
        "board": subject.class_level.board,
        "class_level": subject.class_level,
        "subject": subject,
        "chapters": chapters,
        "papers": QuestionPaper.objects.published().filter(subject=subject)[:6],
        "tests": Test.objects.published().filter(subject=subject)
        .annotate(question_count=Count("test_questions"))[:6],
        "materials": StudyMaterial.objects.published().filter(subject=subject)[:6],
    }
    return render(request, "boards/subject_detail.html", context)


def chapter_detail(request, board_slug, class_slug, subject_slug, chapter_slug):
    subject = _get_subject(board_slug, class_slug, subject_slug)
    chapter = get_object_or_404(subject.chapters.published(), slug=chapter_slug)
    questions = (Question.objects.published().filter(chapter=chapter)
                 .annotate(appearance_years=Count("appearances__year", distinct=True))
                 .prefetch_related("options"))
    log_activity(request.user, UserActivity.Type.VIEW_CHAPTER, f"Opened {chapter.name}", obj=chapter)
    context = {
        "board": subject.class_level.board,
        "class_level": subject.class_level,
        "subject": subject,
        "chapter": chapter,
        "topics": chapter.topics.published(),
        "materials": StudyMaterial.objects.published().filter(chapter=chapter),
        "questions": questions.order_by("-is_important", "-appearance_years")[:10],
        "question_total": questions.count(),
        "pyq": questions.filter(appearance_years__gt=0).order_by("-appearance_years")[:5],
        "tests": Test.objects.published().filter(chapter=chapter)
        .annotate(question_count=Count("test_questions")),
        "papers": QuestionPaper.objects.published().filter(
            Q(chapter=chapter) | Q(subject=subject, paper_type="previous_year"))[:4],
    }
    return render(request, "boards/chapter_detail.html", context)


def topic_detail(request, board_slug, class_slug, subject_slug, chapter_slug, topic_slug):
    subject = _get_subject(board_slug, class_slug, subject_slug)
    chapter = get_object_or_404(subject.chapters.published(), slug=chapter_slug)
    topic = get_object_or_404(chapter.topics.published(), slug=topic_slug)
    context = {
        "board": subject.class_level.board,
        "class_level": subject.class_level,
        "subject": subject,
        "chapter": chapter,
        "topic": topic,
        "materials": StudyMaterial.objects.published().filter(topic=topic),
        "questions": (Question.objects.published().filter(topic=topic)
                      .annotate(appearance_years=Count("appearances__year", distinct=True))
                      .prefetch_related("options")[:20]),
        "sibling_topics": chapter.topics.published().exclude(pk=topic.pk),
    }
    return render(request, "boards/topic_detail.html", context)
