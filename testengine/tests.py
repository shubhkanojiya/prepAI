from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.testing import make_curriculum, make_mcq, make_test, make_user
from questions.models import Question

from . import services
from .models import TestAttempt


class GradingTests(TestCase):
    def setUp(self):
        _, _, self.subject, self.chapter, _ = make_curriculum()
        self.user = make_user()

    def _attempt(self, questions, **kwargs):
        test = make_test(self.subject, self.chapter, questions, **kwargs)
        return services.start_attempt(self.user, test)

    def test_mcq_correct_incorrect_and_negative_marking(self):
        q1, o1 = make_mcq(self.subject, self.chapter, "Q1")
        q2, o2 = make_mcq(self.subject, self.chapter, "Q2")
        q3, _ = make_mcq(self.subject, self.chapter, "Q3")
        attempt = self._attempt([q1, q2, q3], negative="0.25")
        tqs = services.ordered_test_questions(attempt)
        services.save_answer(attempt, tqs[0].id, option_ids=[o1[0].id])   # correct
        services.save_answer(attempt, tqs[1].id, option_ids=[o2[1].id])   # wrong
        attempt = services.submit_attempt(attempt)
        self.assertEqual(attempt.correct_count, 1)
        self.assertEqual(attempt.incorrect_count, 1)
        self.assertEqual(attempt.unanswered_count, 1)
        self.assertEqual(attempt.score, Decimal("0.75"))
        self.assertEqual(attempt.max_score, Decimal("3"))
        self.assertAlmostEqual(attempt.percentage, 25.0)
        self.assertAlmostEqual(attempt.accuracy, 50.0)
        self.assertEqual(attempt.status, TestAttempt.Status.SUBMITTED)

    def test_multi_answer_requires_exact_set(self):
        q = Question.objects.create(subject=self.subject, chapter=self.chapter, text="Pick primes",
                                    question_type=Question.Type.MULTI)
        a = q.options.create(text="2", is_correct=True)
        b = q.options.create(text="3", is_correct=True)
        q.options.create(text="4", is_correct=False)
        attempt = self._attempt([q])
        tq = services.ordered_test_questions(attempt)[0]
        services.save_answer(attempt, tq.id, option_ids=[a.id])
        self.assertEqual(services.submit_attempt(attempt).correct_count, 0)

        attempt2 = services.start_attempt(self.user, tq.test)
        tq2 = services.ordered_test_questions(attempt2)[0]
        services.save_answer(attempt2, tq2.id, option_ids=[a.id, b.id])
        self.assertEqual(services.submit_attempt(attempt2).correct_count, 1)

    def test_numeric_and_fill_blank_grading(self):
        num = Question.objects.create(subject=self.subject, text="5/10", question_type="numeric", answer="0.5")
        fill = Question.objects.create(subject=self.subject, text="sec²θ − tan²θ = __",
                                       question_type="fill_blank", answer="1|one")
        attempt = self._attempt([num, fill])
        tq_num, tq_fill = services.ordered_test_questions(attempt)
        services.save_answer(attempt, tq_num.id, text_answer="0.50")
        services.save_answer(attempt, tq_fill.id, text_answer=" One ")
        self.assertEqual(services.submit_attempt(attempt).correct_count, 2)

    def test_subjective_answers_are_not_auto_graded(self):
        q = Question.objects.create(subject=self.subject, text="Prove it", question_type="long", marks=5)
        attempt = self._attempt([q])
        services.save_answer(attempt, services.ordered_test_questions(attempt)[0].id, text_answer="My proof")
        attempt = services.submit_attempt(attempt)
        self.assertEqual(attempt.ungraded_count, 1)
        self.assertEqual(attempt.max_score, 0)

    def test_single_choice_rejects_multiple_options(self):
        q, opts = make_mcq(self.subject, self.chapter)
        attempt = self._attempt([q])
        with self.assertRaises(services.TestEngineError):
            services.save_answer(attempt, services.ordered_test_questions(attempt)[0].id,
                                 option_ids=[opts[0].id, opts[1].id])

    def test_option_from_another_question_is_rejected(self):
        q1, _ = make_mcq(self.subject, self.chapter, "Q1")
        _, other = make_mcq(self.subject, self.chapter, "Q2")
        attempt = self._attempt([q1])
        with self.assertRaises(services.TestEngineError):
            services.save_answer(attempt, services.ordered_test_questions(attempt)[0].id,
                                 option_ids=[other[0].id])


class LifecycleTests(TestCase):
    def setUp(self):
        _, _, self.subject, self.chapter, _ = make_curriculum()
        self.user = make_user()
        self.q, self.opts = make_mcq(self.subject, self.chapter)

    def test_resume_existing_attempt(self):
        test = make_test(self.subject, self.chapter, [self.q])
        first = services.start_attempt(self.user, test)
        self.assertEqual(services.start_attempt(self.user, test).pk, first.pk)

    def test_expired_attempt_is_auto_submitted_and_rejects_answers(self):
        test = make_test(self.subject, self.chapter, [self.q], duration=1)
        attempt = services.start_attempt(self.user, test)
        TestAttempt.objects.filter(pk=attempt.pk).update(
            deadline=timezone.now() - timedelta(seconds=services.GRACE_SECONDS + 5))
        attempt.refresh_from_db()
        with self.assertRaises(services.TestEngineError):
            services.save_answer(attempt, services.ordered_test_questions(attempt)[0].id,
                                 option_ids=[self.opts[0].id])
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.AUTO_SUBMITTED)

    def test_max_attempts_enforced(self):
        test = make_test(self.subject, self.chapter, [self.q], max_attempts=1)
        services.submit_attempt(services.start_attempt(self.user, test))
        with self.assertRaises(services.TestEngineError):
            services.start_attempt(self.user, test)

    def test_submission_records_performance_and_notification(self):
        test = make_test(self.subject, self.chapter, [self.q])
        attempt = services.start_attempt(self.user, test)
        services.save_answer(attempt, services.ordered_test_questions(attempt)[0].id,
                             option_ids=[self.opts[0].id])
        with self.captureOnCommitCallbacks(execute=True):
            services.submit_attempt(attempt)
        self.assertEqual(self.user.performance_records.count(), 1)
        self.assertTrue(self.user.notifications.filter(notification_type="performance").exists())


class AttemptApiTests(TestCase):
    def setUp(self):
        _, _, self.subject, self.chapter, _ = make_curriculum()
        self.user = make_user()
        self.q, self.opts = make_mcq(self.subject, self.chapter)
        self.test = make_test(self.subject, self.chapter, [self.q])
        self.client.force_login(self.user)

    def test_questions_endpoint_does_not_leak_answers(self):
        attempt = services.start_attempt(self.user, self.test)
        data = self.client.get(reverse("api:attempt-questions", args=[attempt.pk])).json()
        payload = str(data["questions"])
        self.assertNotIn("is_correct", payload)
        self.assertNotIn("explanation", payload)

    def test_other_users_cannot_see_attempt(self):
        attempt = services.start_attempt(self.user, self.test)
        self.client.force_login(make_user("other@example.com"))
        self.assertEqual(self.client.get(reverse("api:attempt-questions", args=[attempt.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("testengine:result", args=[attempt.pk])).status_code, 404)

    def test_answer_and_submit_via_api(self):
        attempt = services.start_attempt(self.user, self.test)
        tq = services.ordered_test_questions(attempt)[0]
        r = self.client.post(reverse("api:attempt-answer", args=[attempt.pk]),
                             {"test_question": tq.id, "options": [self.opts[0].id]}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("api:attempt-submit", args=[attempt.pk]), {}, content_type="application/json")
        self.assertEqual(r.json()["correct_count"], 1)
        # Answers after submission are refused with 409 and a result URL.
        r = self.client.post(reverse("api:attempt-answer", args=[attempt.pk]),
                             {"test_question": tq.id, "options": []}, content_type="application/json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("result_url", r.json())

    def test_result_page_renders(self):
        attempt = services.submit_attempt(services.start_attempt(self.user, self.test))
        self.assertContains(self.client.get(reverse("testengine:result", args=[attempt.pk])), "Question-wise analysis")
