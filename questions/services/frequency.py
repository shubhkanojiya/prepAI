"""
Question Prediction & Frequency Analysis.

IMPORTANT: this module never predicts that a question WILL appear. It only
summarises what is recorded in stored papers (QuestionAppearance rows):
previous appearances, frequency, recency, repeated concepts, and a
transparent, rule-based "preparation priority" derived from those numbers.
"""
from django.db.models import Count, IntegerField, Max, OuterRef, Q, Subquery

from boards.models import Chapter

from ..models import Concept, Question, QuestionAppearance

DISCLAIMER = "Historical analysis does not guarantee appearance in a future examination."


def _board_id(question):
    return question.subject.class_level.board_id


def _reference_year(subject):
    """Latest examination year stored for this subject (recency is measured from it)."""
    return (QuestionAppearance.objects.filter(question__subject=subject)
            .aggregate(y=Max("year"))["y"])


def compute_priority(distinct_years, years_since_last, concept_years):
    """
    Transparent scoring (0–100):
      * frequency  — up to 50 pts (10 per distinct year, capped at 5 years)
      * recency    — up to 30 pts (appeared in the latest 2 / 4 / 6 years of data)
      * concept    — up to 20 pts (how often the underlying concepts recur)
    """
    reasons = []
    frequency_pts = min(distinct_years, 5) * 10
    if distinct_years:
        reasons.append(f"Appeared in {distinct_years} previous year(s)")

    recency_pts = 0
    if years_since_last is not None:
        if years_since_last <= 1:
            recency_pts = 30
        elif years_since_last <= 3:
            recency_pts = 20
        elif years_since_last <= 5:
            recency_pts = 10
        if recency_pts:
            reasons.append("Appeared recently in the stored papers")

    concept_pts = min(concept_years, 5) * 4
    if concept_years >= 2:
        reasons.append(f"Related concepts appeared in {concept_years} year(s)")

    score = frequency_pts + recency_pts + concept_pts
    if distinct_years == 0 and concept_years == 0:
        level = "Insufficient data"
    elif score >= 60:
        level = "High"
    elif score >= 30:
        level = "Medium"
    else:
        level = "Low"
    return {"level": level, "score": score, "reasons": reasons}


def pattern_label(distinct_years, concept_years):
    if distinct_years >= 3:
        return "Frequently appearing concept"
    if distinct_years == 2:
        return "Repeated concept"
    if distinct_years == 1:
        return "Previous appearance (once)"
    if concept_years >= 2:
        return "Related concept appeared previously"
    return "No recorded previous appearances"


def analyze_question(question):
    """Full historical analysis for one question (computed from stored data only)."""
    board_id = _board_id(question)

    # Exact repeats: same normalized text within the same board count as one history.
    group_ids = list(
        Question.objects.filter(fingerprint=question.fingerprint,
                                subject__class_level__board_id=board_id)
        .values_list("id", flat=True)
    ) or [question.id]

    appearances = list(
        QuestionAppearance.objects.filter(question_id__in=group_ids)
        .select_related("paper").order_by("year")
    )
    years = sorted({a.year for a in appearances})
    reference_year = _reference_year(question.subject)
    years_since_last = (reference_year - years[-1]) if (years and reference_year) else None

    concept_rows = []
    for concept in question.concepts.all():
        concept_years = sorted(set(
            QuestionAppearance.objects.filter(
                question__concepts=concept,
                question__subject__class_level__board_id=board_id,
            ).values_list("year", flat=True)
        ))
        concept_rows.append({"concept": concept, "years": concept_years,
                             "count": len(concept_years)})
    concept_rows.sort(key=lambda r: -r["count"])
    max_concept_years = concept_rows[0]["count"] if concept_rows else 0

    return {
        "has_data": bool(appearances) or max_concept_years > 0,
        "appearances": [
            {"year": a.year, "paper": a.paper, "question_number": a.question_number,
             "marks": a.marks}
            for a in appearances
        ],
        "years": years,
        "frequency": len(years),
        "total_appearances": len(appearances),
        "first_year": years[0] if years else None,
        "last_year": years[-1] if years else None,
        "reference_year": reference_year,
        "pattern": pattern_label(len(years), max_concept_years),
        "priority": compute_priority(len(years), years_since_last, max_concept_years),
        "related_concepts": concept_rows,
        "similar_questions": similar_questions(question, exclude_ids=group_ids),
        "disclaimer": DISCLAIMER,
        "contains_sample_data": any(a.paper.is_sample for a in appearances),
    }


def similar_questions(question, exclude_ids=None, limit=5):
    """Questions sharing concepts (or topic) with this one, ranked by overlap and history."""
    concept_ids = list(question.concepts.values_list("id", flat=True))
    criteria = Q(concepts__in=concept_ids) if concept_ids else Q()
    if question.topic_id:
        criteria |= Q(topic_id=question.topic_id)
    if not criteria:
        return []
    return list(
        Question.objects.published()
        .filter(criteria, subject__class_level__board_id=_board_id(question))
        .exclude(id__in=exclude_ids or [question.id])
        .annotate(shared=Count("concepts", filter=Q(concepts__in=concept_ids), distinct=True),
                  appearance_years=Count("appearances__year", distinct=True))
        .order_by("-shared", "-appearance_years")
        .distinct()[:limit]
    )


def subject_overview(subject, limit=15):
    """Most repeated questions, chapters and concepts for a subject."""
    questions = (
        Question.objects.published().filter(subject=subject)
        .annotate(appearance_years=Count("appearances__year", distinct=True),
                  last_year=Max("appearances__year"))
        .filter(appearance_years__gt=0)
        .select_related("chapter")
        .order_by("-appearance_years", "-last_year")[:limit]
    )
    chapters = (
        Chapter.objects.filter(subject=subject)
        .annotate(appearances=Count("questions__appearances"),
                  appearance_years=Count("questions__appearances__year", distinct=True))
        .filter(appearances__gt=0).order_by("-appearances")
    )
    concepts = (
        Concept.objects.filter(subject=subject)
        .annotate(appearances=Count("questions__appearances"),
                  appearance_years=Count("questions__appearances__year", distinct=True))
        .filter(appearances__gt=0).order_by("-appearance_years", "-appearances")[:limit]
    )
    reference_year = _reference_year(subject)
    rows = []
    for q in questions:
        since = reference_year - q.last_year if reference_year and q.last_year else None
        rows.append({"question": q, "years": q.appearance_years, "last_year": q.last_year,
                     "priority": compute_priority(q.appearance_years, since, 0)["level"],
                     "pattern": pattern_label(q.appearance_years, 0)})
    return {
        "questions": rows,
        "chapters": list(chapters),
        "concepts": list(concepts),
        "papers_analyzed": QuestionAppearance.objects.filter(question__subject=subject)
        .values("paper").distinct().count(),
        "reference_year": reference_year,
        "disclaimer": DISCLAIMER,
    }


def important_questions_for_paper(paper, limit=10):
    """Questions in a paper ranked by how often they appear across all stored papers."""
    # Subquery so the count spans ALL stored papers, not just this one.
    years_across_papers = (
        QuestionAppearance.objects.filter(question=OuterRef("pk"))
        .values("question").annotate(c=Count("year", distinct=True)).values("c")
    )
    return list(
        Question.objects.published()
        .filter(id__in=paper.appearances.values("question_id"))
        .annotate(appearance_years=Subquery(years_across_papers, output_field=IntegerField()))
        .order_by("-appearance_years", "-is_important")[:limit]
    )
