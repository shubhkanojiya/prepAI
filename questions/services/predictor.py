"""
Exam Question Predictor.

Given ANY question text (typed, pasted or detected by the AI scanner):

1. Find matching questions in the question bank (exact repeats, very similar
   wording, related questions) using text similarity.
2. Collect their recorded appearances in stored previous-year papers:
   how many times, which years, which papers.
3. Produce a *history-based likelihood estimate* for the upcoming exam, plus
   the recurrence pattern (e.g. "appears about every 2 years").

The estimate is computed only from stored papers and is always shown with a
disclaimer — it is a study aid, never a guarantee. Every number can be traced
back to QuestionAppearance rows.
"""
from collections import defaultdict
from difflib import SequenceMatcher
from statistics import mean

from django.db.models import Count, Q
from django.utils import timezone

from core.utils import normalize_text, text_fingerprint

from ..models import Concept, Question, QuestionAppearance
from .frequency import DISCLAIMER

MATCH_SAME = 0.82        # treated as the same question (repeat)
MATCH_SIMILAR = 0.55     # very similar wording — counted in the history
MATCH_RELATED = 0.35     # related — shown, but not counted
MAX_CANDIDATES = 400
MAX_LIKELIHOOD = 0.85    # never show certainty
MIN_LIKELIHOOD = 0.03

STOPWORDS = set("""
a an the of to in on at for and or but is are was were be been being this that these those it its
by with as from into than then so if what which who whom whose why how when where do does did can
could should would will shall may might must has have had not no yes all any each both few more most
other some such only own same too very just also about above below up down out over under again
further once here there your you i me my we our they them their he she his her find give write
state explain describe define following question answer marks mark show prove
""".split())


def content_tokens(text):
    return [t for t in normalize_text(text).split() if t not in STOPWORDS and (len(t) > 1 or t.isdigit())]


def similarity(query_text, query_tokens, candidate_text):
    """0..1 similarity: exact fingerprint → 1; otherwise token overlap + sequence ratio."""
    if text_fingerprint(query_text) == text_fingerprint(candidate_text):
        return 1.0
    cand_tokens = set(content_tokens(candidate_text))
    q_tokens = set(query_tokens)
    if not q_tokens or not cand_tokens:
        return 0.0
    jaccard = len(q_tokens & cand_tokens) / len(q_tokens | cand_tokens)
    containment = len(q_tokens & cand_tokens) / len(q_tokens)  # handles short queries
    sequence = SequenceMatcher(None, normalize_text(query_text), normalize_text(candidate_text)).ratio()
    return round(0.35 * jaccard + 0.25 * containment + 0.40 * sequence, 3)


def _scope_filter(prefix, board=None, class_level=None, subject=None):
    q = Q()
    if subject:
        q &= Q(**{f"{prefix}subject_id": subject})
    elif class_level:
        q &= Q(**{f"{prefix}subject__class_level_id": class_level})
    elif board:
        q &= Q(**{f"{prefix}subject__class_level__board_id": board})
    return q


def _candidates(tokens, scope_q):
    """Pre-filter with the most distinctive keywords so the scan stays fast on big banks."""
    qs = (Question.objects.published().filter(scope_q)
          .select_related("subject__class_level__board", "chapter")
          .annotate(appearance_count=Count("appearances")))
    keywords = sorted({t for t in tokens if len(t) >= 3}, key=len, reverse=True)[:6]
    if keywords:
        keyword_q = Q()
        for kw in keywords:
            keyword_q |= Q(text__icontains=kw)
        qs = qs.filter(keyword_q)
    return list(qs.order_by("-appearance_count", "-created_at")[:MAX_CANDIDATES])


def upcoming_exam_year(today=None):
    """Board exams are held Feb–Apr; after April the next exam is next year's."""
    today = today or timezone.localdate()
    return today.year + 1 if today.month > 4 else today.year


def recurrence_pattern(years, upcoming_year):
    """Average gap between appearances and the year the pattern points to next."""
    if len(years) < 2:
        return None
    gaps = [b - a for a, b in zip(years, years[1:]) if b > a]
    if not gaps:
        return None
    avg_gap = mean(gaps)
    step = max(1, round(avg_gap))
    next_year = years[-1] + step
    while next_year < upcoming_year:  # skip years the pattern already "missed"
        next_year += step
    if avg_gap <= 1.2:
        label = "Appears almost every year"
    else:
        label = f"Appears about every {avg_gap:.1f} years".replace(".0 ", " ")
    return {
        "average_gap": round(avg_gap, 1),
        "gaps": gaps,
        "label": label,
        "next_expected_year": next_year,
        "due_in_upcoming_exam": next_year == upcoming_year,
    }


def estimate_likelihood(appeared_years, available_years, concept_years=0, pattern=None):
    """
    History-based likelihood (0.03–0.85) that the question (or a close variant)
    appears in the upcoming exam. Transparent weighting:

      60%  appearance rate  = (years appeared + 0.5) / (years of papers stored + 1)
      25%  recency          = how recently it last appeared in the stored papers
      15%  concept rate     = share of stored years in which its concepts appeared
      +5 points if the recurrence pattern points to the upcoming exam year

    Returns None when no papers are stored for the scope (nothing to base it on).
    """
    if not available_years:
        return None
    n_avail = len(available_years)
    k = len(appeared_years)
    rate = (k + 0.5) / (n_avail + 1)          # smoothed so it's never exactly 0% or 100%

    recency = 0.0
    since = None
    if k:
        since = max(available_years) - max(appeared_years)
        recency = 1.0 if since <= 1 else 0.7 if since <= 3 else 0.4 if since <= 5 else 0.2
    concept_rate = min(concept_years / n_avail, 1.0) if n_avail else 0.0

    score = 0.60 * rate + 0.25 * recency + 0.15 * concept_rate
    reasons = [f"Appeared in {k} of the {n_avail} year(s) of stored papers"]
    if since is not None:
        reasons.append("Appeared in the most recent stored paper" if since == 0
                       else f"Last appeared {since} year(s) before the latest stored paper")
    if concept_years:
        reasons.append(f"Its concepts appeared in {concept_years} of {n_avail} stored year(s)")
    if pattern and pattern["due_in_upcoming_exam"]:
        score += 0.05
        reasons.append(f"The recurrence pattern ({pattern['label'].lower()}) points to the upcoming exam")

    score = max(MIN_LIKELIHOOD, min(MAX_LIKELIHOOD, score))
    level = "High" if score >= 0.55 else "Moderate" if score >= 0.30 else "Low"
    return {"probability": round(score, 2), "percent": round(score * 100), "level": level,
            "reasons": reasons}


def predict(text, board=None, class_level=None, subject=None):
    """Full prediction report for a free-text question."""
    text = (text or "").strip()[:2000]
    tokens = content_tokens(text)
    upcoming = upcoming_exam_year()
    report = {"query": text, "upcoming_year": upcoming, "disclaimer": DISCLAIMER, "has_matches": False,
              "matches": [], "related": [], "appearances": [], "years": [], "times_appeared": 0,
              "available_years": [], "pattern": None, "likelihood": None, "concepts": [],
              "subject": None, "contains_sample_data": False}
    if not tokens:
        return report

    scored = []
    for question in _candidates(tokens, _scope_filter("", board, class_level, subject)):
        score = similarity(text, tokens, question.text)
        if score >= MATCH_RELATED:
            scored.append((score, question))
    scored.sort(key=lambda pair: (-pair[0], -pair[1].appearance_count))

    def match_type(score):
        return "Same question" if score >= MATCH_SAME else "Very similar" if score >= MATCH_SIMILAR else "Related"

    counted = [(s, q) for s, q in scored if s >= MATCH_SIMILAR][:10]
    report["matches"] = [{"question": q, "score": s, "percent": round(s * 100), "type": match_type(s),
                          "appearances": q.appearance_count} for s, q in counted]
    report["related"] = [{"question": q, "percent": round(s * 100), "appearances": q.appearance_count}
                         for s, q in scored if s < MATCH_SIMILAR][:6]

    # Concepts named in the query text (useful even without a close match).
    normalized_query = f" {normalize_text(text)} "
    concept_scope = _scope_filter("", board, class_level, subject)
    concepts = [c for c in Concept.objects.filter(concept_scope).select_related("subject")
                if f" {normalize_text(c.name)} " in normalized_query]

    anchor_subject = counted[0][1].subject if counted else (concepts[0].subject if concepts else None)
    report["subject"] = anchor_subject
    if anchor_subject is None:
        return report

    # Years for which previous-year papers are stored for this subject.
    report["available_years"] = sorted(set(
        QuestionAppearance.objects.filter(question__subject=anchor_subject).values_list("year", flat=True)
    ) | set(anchor_subject.papers.published().filter(paper_type="previous_year", year__isnull=False)
            .values_list("year", flat=True)))

    appearances = (QuestionAppearance.objects.filter(question_id__in=[q.id for _s, q in counted])
                   .select_related("paper", "question").order_by("year"))
    by_year = defaultdict(list)
    for a in appearances:
        by_year[a.year].append(a)
    report["appearances"] = [
        {"year": year, "papers": sorted({a.paper for a in items}, key=lambda p: p.title),
         "question_numbers": [a.question_number for a in items if a.question_number],
         "marks": next((a.marks for a in items if a.marks), None)}
        for year, items in sorted(by_year.items())
    ]
    report["years"] = sorted(by_year)
    report["times_appeared"] = len(report["years"])
    report["total_appearances"] = sum(len(v) for v in by_year.values())
    report["contains_sample_data"] = any(a.paper.is_sample for a in appearances)
    report["has_matches"] = bool(counted)

    concept_ids = {c.id for c in concepts} | set(
        Concept.objects.filter(questions__in=[q.id for _s, q in counted[:3]]).values_list("id", flat=True))
    concept_years = set()
    concept_rows = []
    for concept in Concept.objects.filter(id__in=concept_ids):
        years = sorted(set(QuestionAppearance.objects.filter(question__concepts=concept)
                           .values_list("year", flat=True)))
        concept_years |= set(years)
        concept_rows.append({"concept": concept, "years": years, "count": len(years)})
    report["concepts"] = sorted(concept_rows, key=lambda r: -r["count"])

    report["pattern"] = recurrence_pattern(report["years"], upcoming)
    report["likelihood"] = estimate_likelihood(report["years"], report["available_years"],
                                               len(concept_years), report["pattern"])
    return report


def predict_for_question(question):
    """Prediction block for a question already in the bank (used on its detail page)."""
    report = predict(question.text, subject=question.subject_id)
    return {k: report[k] for k in ("years", "times_appeared", "available_years", "pattern",
                                   "likelihood", "upcoming_year")}
