"""Previous-year paper archive: the subject × year grid used by the archive and subject pages."""
from collections import defaultdict

from django.utils import timezone

from .models import QuestionPaper

ARCHIVE_YEARS = 5
# Board results are out by May, so that year's papers count as "previous year" from then on.
NEW_SESSION_MONTH = 5

EXAM_ORDER = {value: i for i, value in enumerate(QuestionPaper.ExamType.values)}


def recent_exam_years(count=ARCHIVE_YEARS, today=None):
    """The last `count` board-exam years, newest first."""
    today = today or timezone.localdate()
    latest = today.year if today.month >= NEW_SESSION_MONTH else today.year - 1
    return list(range(latest, latest - count, -1))


def year_grid(subjects, years=None, exam_type=None):
    """
    Return one row per subject: {"subject", "cells": [{"year", "papers"}], "available"}.
    Papers in a cell are ordered annual → supplementary → other exam types; demo papers
    are dropped from a cell once a real paper exists for it.
    """
    years = years or recent_exam_years()
    subjects = list(subjects)
    found = defaultdict(list)
    papers = (QuestionPaper.objects.published()
              .filter(paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR,
                      subject__in=subjects, year__in=years)
              .exclude(pdf="")  # e.g. a solution-only import: nothing to open
              .only("id", "slug", "title", "year", "exam_type", "subject_id", "pdf", "is_sample"))
    if exam_type:
        papers = papers.filter(exam_type=exam_type)
    for paper in papers:
        found[(paper.subject_id, paper.year)].append(paper)
    rows = []
    for subject in subjects:
        cells = []
        for year in years:
            cell_papers = found[(subject.id, year)]
            if any(not p.is_sample for p in cell_papers):
                cell_papers = [p for p in cell_papers if not p.is_sample]
            cell_papers = sorted(cell_papers, key=lambda p: EXAM_ORDER.get(p.exam_type, 99))
            cells.append({"year": year, "papers": cell_papers})
        rows.append({"subject": subject, "cells": cells,
                     "available": sum(1 for c in cells if c["papers"])})
    return rows


def chapter_questions(chapter, years, exam_type=None):
    """
    Questions from `chapter` recorded in previous-year papers of `years`, newest first:
    [{"question", "appearances": [QuestionAppearance, ...]}]. Board papers cover the whole
    syllabus, so this is how a chapter narrows them down.
    """
    from questions.models import QuestionAppearance

    appearances = (QuestionAppearance.objects
                   .filter(question__chapter=chapter, question__is_published=True,
                           paper__is_published=True, year__in=years,
                           paper__paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR)
                   .select_related("question", "paper").order_by("-year", "question_number"))
    if exam_type:
        appearances = appearances.filter(paper__exam_type=exam_type)
    grouped = {}
    for appearance in appearances:
        grouped.setdefault(appearance.question_id, {"question": appearance.question, "appearances": []})
        grouped[appearance.question_id]["appearances"].append(appearance)
    return list(grouped.values())
