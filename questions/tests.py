from django.test import TestCase
from django.urls import reverse

from core.testing import add_appearance, make_concept, make_curriculum, make_mcq, make_paper

from .models import Question
from .services.frequency import DISCLAIMER, analyze_question, compute_priority, important_questions_for_paper


class FrequencyAnalysisTests(TestCase):
    def setUp(self):
        _, _, self.subject, self.chapter, _ = make_curriculum()
        self.question = Question.objects.create(subject=self.subject, chapter=self.chapter,
                                                text="Explain Newton's laws of motion.", question_type="long")
        self.papers = {y: make_paper(self.subject, y) for y in (2019, 2021, 2023, 2025)}

    def test_counts_come_only_from_stored_appearances(self):
        for year in (2019, 2021, 2023, 2025):
            add_appearance(self.question, self.papers[year])
        analysis = analyze_question(self.question)
        self.assertEqual(analysis["years"], [2019, 2021, 2023, 2025])
        self.assertEqual(analysis["frequency"], 4)
        self.assertEqual(analysis["pattern"], "Frequently appearing concept")
        self.assertEqual(analysis["priority"]["level"], "High")
        self.assertEqual(analysis["disclaimer"], DISCLAIMER)

    def test_no_data_is_reported_honestly(self):
        analysis = analyze_question(self.question)
        self.assertFalse(analysis["has_data"])
        self.assertEqual(analysis["frequency"], 0)
        self.assertEqual(analysis["priority"]["level"], "Insufficient data")
        self.assertEqual(analysis["pattern"], "No recorded previous appearances")

    def test_identical_text_counts_as_repeat(self):
        twin = Question.objects.create(subject=self.subject, text="explain newtons laws of motion",
                                       question_type="long")
        add_appearance(self.question, self.papers[2019])
        add_appearance(twin, self.papers[2023])
        self.assertEqual(analyze_question(self.question)["years"], [2019, 2023])

    def test_concept_history_and_similar_questions(self):
        force = make_concept(self.subject, "Force")
        self.question.concepts.add(force)
        other = Question.objects.create(subject=self.subject, text="Define force.", question_type="short")
        other.concepts.add(force)
        add_appearance(other, self.papers[2021])
        add_appearance(other, self.papers[2023], number="2")
        analysis = analyze_question(self.question)
        self.assertEqual(analysis["related_concepts"][0]["count"], 2)
        self.assertIn(other, analysis["similar_questions"])
        self.assertEqual(analysis["pattern"], "Related concept appeared previously")

    def test_priority_scoring_rules(self):
        self.assertEqual(compute_priority(0, None, 0)["level"], "Insufficient data")
        self.assertEqual(compute_priority(1, 8, 0)["level"], "Low")
        self.assertEqual(compute_priority(2, 2, 0)["level"], "Medium")
        self.assertEqual(compute_priority(5, 0, 5)["score"], 100)

    def test_important_questions_count_across_all_papers(self):
        add_appearance(self.question, self.papers[2019])
        add_appearance(self.question, self.papers[2021])
        top = important_questions_for_paper(self.papers[2019])
        self.assertEqual(top[0].appearance_years, 2)

    def test_question_page_shows_disclaimer(self):
        response = self.client.get(reverse("questions:detail", args=[self.question.pk]))
        self.assertContains(response, DISCLAIMER)

    def test_frequency_api(self):
        add_appearance(self.question, self.papers[2023])
        data = self.client.get(reverse("api:question-frequency", args=[self.question.pk])).json()
        self.assertEqual(data["years"], [2023])
        self.assertEqual(data["disclaimer"], DISCLAIMER)


class PredictorTests(TestCase):
    def setUp(self):
        _, self.class_level, self.subject, self.chapter, _ = make_curriculum()
        self.question = Question.objects.create(subject=self.subject, chapter=self.chapter,
                                                text="Explain Newton's laws of motion.", question_type="long")
        self.papers = {y: make_paper(self.subject, y) for y in (2019, 2020, 2021, 2022, 2023, 2025)}
        for year in (2019, 2021, 2023, 2025):
            add_appearance(self.question, self.papers[year])

    def test_reworded_question_matches_and_reports_years(self):
        from .services.predictor import predict

        report = predict("explain newtons three laws of motion")
        self.assertTrue(report["has_matches"])
        self.assertEqual(report["matches"][0]["question"], self.question)
        self.assertEqual(report["times_appeared"], 4)
        self.assertEqual(report["years"], [2019, 2021, 2023, 2025])
        self.assertEqual(report["available_years"], [2019, 2020, 2021, 2022, 2023, 2025])
        self.assertEqual(report["disclaimer"], DISCLAIMER)

    def test_likelihood_is_bounded_and_explained(self):
        from .services.predictor import MAX_LIKELIHOOD, MIN_LIKELIHOOD, estimate_likelihood, predict

        likelihood = predict("Explain Newton's laws of motion.")["likelihood"]
        self.assertLessEqual(likelihood["probability"], MAX_LIKELIHOOD)
        self.assertEqual(likelihood["level"], "High")
        self.assertTrue(likelihood["reasons"])
        # Never appeared → low but never 0%; nothing stored → no estimate at all.
        low = estimate_likelihood([], [2019, 2020, 2021, 2022, 2023])
        self.assertEqual(low["level"], "Low")
        self.assertGreaterEqual(low["probability"], MIN_LIKELIHOOD)
        self.assertIsNone(estimate_likelihood([2020], []))

    def test_recurrence_pattern(self):
        from .services.predictor import recurrence_pattern

        pattern = recurrence_pattern([2019, 2021, 2023, 2025], upcoming_year=2027)
        self.assertEqual(pattern["average_gap"], 2)
        self.assertEqual(pattern["next_expected_year"], 2027)
        self.assertTrue(pattern["due_in_upcoming_exam"])
        self.assertIsNone(recurrence_pattern([2023], upcoming_year=2027))
        # A "missed" slot rolls forward instead of predicting a past year.
        self.assertEqual(recurrence_pattern([2015, 2017], upcoming_year=2026)["next_expected_year"], 2027)

    def test_unrelated_question_has_no_history(self):
        from .services.predictor import predict

        report = predict("What is the capital of France?")
        self.assertFalse(report["has_matches"])
        self.assertIsNone(report["likelihood"])
        self.assertEqual(report["times_appeared"], 0)

    def test_scope_filter_excludes_other_subjects(self):
        from .services.predictor import predict

        _, _, other_subject, _, _ = make_curriculum("icse")
        self.assertFalse(predict("Explain Newton's laws of motion.", subject=other_subject.id)["has_matches"])

    def test_predictor_page(self):
        response = self.client.get(reverse("questions:predictor"), {"q": "Explain Newton's laws of motion"})
        self.assertContains(response, "Times appeared")
        self.assertContains(response, "2025")
        self.assertContains(response, DISCLAIMER)
        self.assertContains(self.client.get(reverse("questions:predictor")), "Exam Question Predictor")

    def test_predict_api(self):
        r = self.client.post(reverse("api:question-predict"), {"text": "Explain Newton's laws of motion"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["times_appeared"], 4)
        self.assertEqual(data["years"], [2019, 2021, 2023, 2025])
        self.assertIn("percent", data["likelihood"])
        self.assertEqual(data["disclaimer"], DISCLAIMER)
        self.assertEqual(self.client.post(reverse("api:question-predict"), {},
                                          content_type="application/json").status_code, 400)


class QuestionApiPermissionTests(TestCase):
    def test_students_cannot_create_questions(self):
        from core.testing import make_user

        _, _, subject, chapter, _ = make_curriculum()
        self.client.force_login(make_user())
        r = self.client.post(reverse("api:question-list"), {"subject": subject.id, "text": "x"})
        self.assertEqual(r.status_code, 403)

    def test_unpublished_questions_hidden(self):
        _, _, subject, chapter, _ = make_curriculum()
        q, _ = make_mcq(subject, chapter)
        q.is_published = False
        q.save()
        self.assertEqual(self.client.get(reverse("questions:detail", args=[q.pk])).status_code, 404)
