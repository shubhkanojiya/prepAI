"""
Rule-based recommendation engine.

1. Weak chapters (low accuracy in recorded performance) → revision material,
   a chapter test, frequently repeated questions and previous-year papers.
2. Fallback for new students → featured content for their board/class.

The engine is deliberately transparent: every recommendation stores a
human-readable `reason`. It can later be replaced by an ML model behind the
same `generate_for_user` / `get_for_user` functions.
"""
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from analytics.services import weak_and_strong_areas
from boards.models import Chapter
from content.models import StudyMaterial
from papers.models import QuestionPaper
from questions.models import Question
from testengine.models import Test, TestAttempt

from .models import Recommendation

MAX_RECOMMENDATIONS = 12
STALE_AFTER = timedelta(hours=24)
MATERIAL_PRIORITY = ["revision", "summary", "important_questions", "formula", "concept", "notes", "pdf"]


def _candidates_for_weak_chapter(user, chapter_row):
    chapter = Chapter.objects.select_related("subject").get(pk=chapter_row["chapter_id"])
    urgency = 100 - chapter_row["accuracy"]
    reason_base = f"{chapter.name}: {chapter_row['accuracy']:.0f}% accuracy"
    items = []

    materials = list(StudyMaterial.objects.published().filter(chapter=chapter))
    materials.sort(key=lambda m: MATERIAL_PRIORITY.index(m.material_type)
                   if m.material_type in MATERIAL_PRIORITY else 99)
    for m in materials[:2]:
        rec_type = Recommendation.Type.REVISION if m.material_type == "revision" else Recommendation.Type.MATERIAL
        items.append((rec_type, m, f"Revise — {reason_base}", urgency + 5))

    attempted_test_ids = TestAttempt.objects.filter(user=user).values("test_id")
    tests = (Test.objects.published().filter(chapter=chapter)
             .exclude(id__in=attempted_test_ids)[:1]
             or Test.objects.published().filter(chapter=chapter)[:1])
    for t in tests:
        items.append((Recommendation.Type.TEST, t, f"Practise — {reason_base}", urgency + 3))

    questions = (Question.objects.published().filter(chapter=chapter)
                 .annotate(n=Count("appearances__year", distinct=True))
                 .filter(n__gt=0).order_by("-n")[:2])
    for q in questions:
        items.append((Recommendation.Type.QUESTION, q,
                      f"Previously asked {q.n} time(s) — {chapter.name}", urgency))

    papers = QuestionPaper.objects.published().filter(
        subject=chapter.subject, paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR)[:1]
    for p in papers:
        items.append((Recommendation.Type.PAPER, p,
                      f"Previous-year paper for {chapter.subject.name}", urgency - 5))

    items.append((Recommendation.Type.CHAPTER, chapter, f"Focus area — {reason_base}", urgency - 2))
    return items


def _fallback_candidates(user):
    profile = getattr(user, "profile", None)
    tests = Test.objects.published()
    materials = StudyMaterial.objects.published()
    papers = QuestionPaper.objects.published().filter(paper_type=QuestionPaper.PaperType.PREVIOUS_YEAR)
    context = "for you"
    if profile and profile.class_level_id:
        tests = tests.filter(class_level_id=profile.class_level_id)
        materials = materials.filter(subject__class_level_id=profile.class_level_id)
        papers = papers.filter(subject__class_level_id=profile.class_level_id)
        context = f"for {profile.class_level}"
    elif profile and profile.board_id:
        tests = tests.filter(board_id=profile.board_id)
        materials = materials.filter(subject__class_level__board_id=profile.board_id)
        papers = papers.filter(subject__class_level__board_id=profile.board_id)
        context = f"for {profile.board}"

    items = []
    for t in tests.order_by("-is_featured", "-created_at")[:3]:
        items.append((Recommendation.Type.TEST, t, f"Popular test {context}", 30))
    for m in materials.order_by("-is_featured", "-created_at")[:3]:
        items.append((Recommendation.Type.MATERIAL, m, f"Recommended reading {context}", 25))
    for p in papers.order_by("-year")[:2]:
        items.append((Recommendation.Type.PAPER, p, f"Latest previous-year paper {context}", 20))
    return items


@transaction.atomic
def generate_for_user(user):
    weak, _strong = weak_and_strong_areas(user, min_attempted=2)
    candidates = []
    for row in weak[:3]:
        candidates.extend(_candidates_for_weak_chapter(user, row))
    if len(candidates) < 6:
        candidates.extend(_fallback_candidates(user))

    dismissed = set(Recommendation.objects.filter(user=user, is_dismissed=True)
                    .values_list("content_type_id", "object_id"))
    Recommendation.objects.filter(user=user, is_dismissed=False).delete()

    seen, new = set(), []
    for rec_type, obj, reason, score in sorted(candidates, key=lambda c: -c[3]):
        key = (ContentType.objects.get_for_model(obj).id, obj.pk)
        if key in seen or key in dismissed:
            continue
        seen.add(key)
        new.append(Recommendation(user=user, rec_type=rec_type, content_type_id=key[0],
                                  object_id=obj.pk, reason=reason[:255], score=score))
        if len(new) >= MAX_RECOMMENDATIONS:
            break
    Recommendation.objects.bulk_create(new, ignore_conflicts=True)  # concurrent page loads
    return new


def get_for_user(user, limit=6, rec_types=None):
    qs = Recommendation.objects.filter(user=user, is_dismissed=False)
    newest = qs.order_by("-created_at").values_list("created_at", flat=True).first()
    if newest is None or timezone.now() - newest > STALE_AFTER:
        generate_for_user(user)
    qs = Recommendation.objects.filter(user=user, is_dismissed=False)
    if rec_types:
        qs = qs.filter(rec_type__in=rec_types)
    recs = list(qs.select_related("content_type").prefetch_related("content_object")[:limit])
    return [r for r in recs if r.content_object is not None]
