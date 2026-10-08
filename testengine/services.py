"""
Test engine: start → save answers → submit (manual or automatic) → grade → results.

The server is the source of truth for time: answers arriving after the
deadline (plus a small network grace period) are rejected, and expired
attempts are auto-submitted whenever they are next accessed.
"""
import logging
import random
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.utils import normalize_text
from questions.models import Question

from .models import TestAnswer, TestAttempt, TestQuestion

logger = logging.getLogger("prepai.testengine")

GRACE_SECONDS = 30


class TestEngineError(Exception):
    pass


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def start_attempt(user, test):
    """Resume the user's active attempt or start a new one."""
    with transaction.atomic():
        # Lock the user row so a double-click can't create two attempts (or exceed max_attempts).
        list(type(user).objects.select_for_update().filter(pk=user.pk).values_list("pk", flat=True))
        return _start_attempt(user, test)


def _start_attempt(user, test):
    active = TestAttempt.objects.filter(user=user, test=test,
                                        status=TestAttempt.Status.IN_PROGRESS).first()
    if active:
        active = expire_if_needed(active)
        if active.is_in_progress:
            return active

    if test.max_attempts:
        used = TestAttempt.objects.filter(user=user, test=test).count()
        if used >= test.max_attempts:
            raise TestEngineError("You have used all attempts allowed for this test.")

    test_questions = list(test.test_questions.filter(question__is_published=True)
                          .values_list("id", flat=True))
    if not test_questions:
        raise TestEngineError("This test has no questions yet.")
    if test.shuffle_questions:
        random.shuffle(test_questions)

    with transaction.atomic():
        attempt = TestAttempt.objects.create(user=user, test=test, question_order=test_questions)
        TestAnswer.objects.bulk_create(
            [TestAnswer(attempt=attempt, test_question_id=tq_id) for tq_id in test_questions]
        )

    from analytics.models import UserActivity
    from analytics.services import log_activity

    log_activity(user, UserActivity.Type.START_TEST, f"Started {test.title}", obj=test)
    return attempt


def locked_question_ids(user):
    """
    Questions in the user's unfinished tests. Their answers stay hidden in the question bank
    until the test is submitted, so a student can't look them up mid-test.
    """
    if not getattr(user, "is_authenticated", False):
        return set()
    active = [expire_if_needed(a) for a in TestAttempt.objects.filter(
        user=user, status=TestAttempt.Status.IN_PROGRESS).select_related("test")]
    test_ids = [a.test_id for a in active if a.is_in_progress]
    if not test_ids:
        return set()
    return set(TestQuestion.objects.filter(test_id__in=test_ids).values_list("question_id", flat=True))


def expire_if_needed(attempt):
    """Auto-submit an in-progress attempt whose time (plus grace) has run out."""
    if attempt.is_in_progress and attempt.remaining_seconds == 0:
        overdue = (timezone.now() - attempt.deadline).total_seconds()
        if overdue > GRACE_SECONDS:
            return submit_attempt(attempt, auto=True)
    return attempt


def ordered_test_questions(attempt):
    """TestQuestions (with question + options) in the attempt's display order."""
    tqs = {
        tq.id: tq for tq in TestQuestion.objects.filter(id__in=attempt.question_order)
        .select_related("question", "question__chapter", "question__subject")
        .prefetch_related("question__options")
    }
    return [tqs[i] for i in attempt.question_order if i in tqs]


def save_answer(attempt, test_question_id, option_ids=None, text_answer=None,
                marked_for_review=None, time_spent_seconds=0):
    with transaction.atomic():
        # Lock the attempt so an answer can't land after a concurrent submit has graded it.
        attempt = TestAttempt.objects.select_for_update().select_related("test").get(pk=attempt.pk)
        if not attempt.is_in_progress:
            raise TestEngineError("This test has already been submitted.")
        if (timezone.now() - attempt.deadline).total_seconds() <= GRACE_SECONDS:
            return _write_answer(attempt, test_question_id, option_ids, text_answer,
                                 marked_for_review, time_spent_seconds)
    submit_attempt(attempt, auto=True)  # outside the block above so the raise can't roll it back
    raise TestEngineError("Time is up. Your test was submitted automatically.")


def _write_answer(attempt, test_question_id, option_ids, text_answer, marked_for_review,
                  time_spent_seconds):
    try:
        answer = attempt.answers.select_related("test_question__question").get(
            test_question_id=test_question_id
        )
    except TestAnswer.DoesNotExist:
        raise TestEngineError("This question is not part of your test.")

    question = answer.test_question.question
    answer.visited = True
    if option_ids is not None:
        valid_ids = set(question.options.filter(id__in=option_ids).values_list("id", flat=True))
        if len(valid_ids) != len(set(option_ids)):
            raise TestEngineError("Invalid option selected.")
        if question.question_type != Question.Type.MULTI and len(valid_ids) > 1:
            raise TestEngineError("Only one option can be selected for this question.")
        answer.selected_options.set(valid_ids)
    if text_answer is not None:
        answer.text_answer = text_answer.strip()[:5000]
    if marked_for_review is not None:
        answer.is_marked_for_review = bool(marked_for_review)
    if time_spent_seconds:
        answer.time_spent_seconds = min(answer.time_spent_seconds + int(time_spent_seconds),
                                        attempt.test.duration_minutes * 60)
    answer.save()
    return answer


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
def grade_answer(test_question, answer, selected_ids=None):
    """Return (is_correct: bool|None, marks: Decimal). None = unanswered/ungraded."""
    question = test_question.question
    marks = Decimal(test_question.effective_marks)
    penalty = Decimal(test_question.effective_negative_marks)

    if question.is_objective:
        selected = set(selected_ids if selected_ids is not None
                       else answer.selected_options.values_list("id", flat=True))
        if not selected:
            return None, Decimal(0)
        correct = {o.id for o in question.options.all() if o.is_correct}
        return (True, marks) if selected == correct else (False, -penalty)

    text = (answer.text_answer or "").strip()
    if not text:
        return None, Decimal(0)
    if question.question_type == Question.Type.NUMERIC:
        try:
            given = float(text.replace(",", ""))
            expected = float(question.answer.strip().replace(",", ""))
        except (ValueError, AttributeError):
            return False, -penalty
        ok = abs(given - expected) <= question.numeric_tolerance
        return (True, marks) if ok else (False, -penalty)
    if question.question_type == Question.Type.FILL_BLANK:
        accepted = {normalize_text(a) for a in question.answer.split("|") if a.strip()}
        return (True, marks) if normalize_text(text) in accepted else (False, -penalty)
    return None, Decimal(0)  # subjective: compare with the model answer manually


@transaction.atomic
def submit_attempt(attempt, auto=False):
    attempt = TestAttempt.objects.select_for_update().select_related("test").get(pk=attempt.pk)
    if not attempt.is_in_progress:
        return attempt

    now = timezone.now()
    if now > attempt.deadline:
        auto = True  # past the time limit counts as auto-submitted, whatever the client says
    score = max_score = Decimal(0)
    correct = incorrect = unanswered = ungraded = 0
    answers = attempt.answers.select_related("test_question__question").prefetch_related(
        "selected_options", "test_question__question__options"
    )
    for answer in answers:
        tq = answer.test_question
        question = tq.question
        selected_ids = [o.id for o in answer.selected_options.all()]
        is_correct, marks = grade_answer(tq, answer, selected_ids)
        answer.is_correct, answer.marks_awarded = is_correct, marks
        answer.save(update_fields=["is_correct", "marks_awarded", "updated_at"])

        if question.is_auto_graded:
            max_score += Decimal(tq.effective_marks)
            score += marks
            if is_correct is None:
                unanswered += 1
            elif is_correct:
                correct += 1
            else:
                incorrect += 1
        elif answer.text_answer:
            ungraded += 1
        else:
            unanswered += 1

    attempt.status = TestAttempt.Status.AUTO_SUBMITTED if auto else TestAttempt.Status.SUBMITTED
    attempt.submitted_at = min(now, attempt.deadline) if auto else now
    attempt.time_taken_seconds = max(0, int((attempt.submitted_at - attempt.started_at).total_seconds()))
    attempt.score, attempt.max_score = score, max_score
    attempt.percentage = round(max(float(score), 0) / float(max_score) * 100, 2) if max_score else 0
    attempt.accuracy = round(100 * correct / (correct + incorrect), 2) if (correct + incorrect) else 0
    attempt.correct_count, attempt.incorrect_count = correct, incorrect
    attempt.unanswered_count, attempt.ungraded_count = unanswered, ungraded
    attempt.save()

    transaction.on_commit(lambda: _after_submit(attempt.pk))
    return attempt


def _after_submit(attempt_id):
    """Side effects that must never block or break submission."""
    from analytics.models import UserActivity
    from analytics.services import log_activity, record_attempt_performance
    from notifications.models import Notification
    from notifications.services import notify
    from recommendations.services import generate_for_user

    attempt = TestAttempt.objects.select_related("test", "user").get(pk=attempt_id)
    try:
        record_attempt_performance(attempt)
        log_activity(attempt.user, UserActivity.Type.SUBMIT_TEST,
                     f"Scored {attempt.percentage:.0f}% in {attempt.test.title}", obj=attempt.test,
                     url=attempt.get_absolute_url(), percentage=attempt.percentage)
        notify(attempt.user, Notification.Type.PERFORMANCE,
               f"Result ready: {attempt.test.title}",
               f"You scored {attempt.percentage:.0f}% with {attempt.accuracy:.0f}% accuracy.",
               attempt.get_absolute_url())
        generate_for_user(attempt.user)
    except Exception:
        logger.exception("Post-submission processing failed for attempt %s", attempt_id)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
def build_result(attempt):
    """Question-wise analysis plus subject/chapter breakdown for the result page."""
    answers = {
        a.test_question_id: a
        for a in attempt.answers.prefetch_related("selected_options")
    }
    questions, by_subject, by_chapter = [], defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0, 0])
    for index, tq in enumerate(ordered_test_questions(attempt), start=1):
        answer = answers.get(tq.id)
        question = tq.question
        selected = {o.id for o in answer.selected_options.all()} if answer else set()
        if answer and answer.is_correct is True:
            state = "correct"
        elif answer and answer.is_correct is False:
            state = "incorrect"
        elif answer and answer.text_answer and not question.is_auto_graded:
            state = "ungraded"
        else:
            state = "unanswered"
        questions.append({
            "number": index, "test_question": tq, "question": question, "answer": answer,
            "selected": selected, "state": state,
            "options": [{"option": o, "selected": o.id in selected} for o in question.options.all()],
        })
        if question.is_auto_graded:
            for key, bucket in ((question.subject.name, by_subject),
                                (question.chapter.name if question.chapter else "General", by_chapter)):
                bucket[key][0] += 1
                if state == "correct":
                    bucket[key][1] += 1
                elif state == "incorrect":
                    bucket[key][2] += 1

    def breakdown(bucket):
        rows = []
        for name, (total, right, wrong) in bucket.items():
            attempted = right + wrong
            rows.append({"name": name, "total": total, "correct": right, "incorrect": wrong,
                         "accuracy": round(100 * right / attempted, 1) if attempted else 0,
                         "score_pct": round(100 * right / total, 1) if total else 0})
        return sorted(rows, key=lambda r: r["score_pct"])

    return {
        "questions": questions,
        "subject_breakdown": breakdown(by_subject),
        "chapter_breakdown": breakdown(by_chapter),
    }
