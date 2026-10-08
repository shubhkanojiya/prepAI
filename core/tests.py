"""Cross-cutting tests: validators, pages, accounts, bookmarks, search, recommendations."""
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from bookmarks.models import Bookmark
from content.models import StudyMaterial
from core.testing import add_appearance, make_curriculum, make_mcq, make_paper, make_test, make_user
from core.utils import render_markdown
from core.validators import validate_pdf
from recommendations.services import generate_for_user
from search.models import SearchHistory
from testengine import services as engine


class ValidatorTests(TestCase):
    def test_pdf_magic_bytes_required(self):
        with self.assertRaises(ValidationError):
            validate_pdf(SimpleUploadedFile("fake.pdf", b"<html>not a pdf</html>"))
        validate_pdf(SimpleUploadedFile("real.pdf", b"%PDF-1.4\n%%EOF"))

    def test_pdf_extension_required(self):
        with self.assertRaises(ValidationError):
            validate_pdf(SimpleUploadedFile("paper.exe", b"%PDF-1.4"))

    def test_markdown_escapes_html(self):
        html = render_markdown("<script>alert(1)</script> **bold**")
        self.assertNotIn("<script>", html)
        self.assertIn("<strong>bold</strong>", html)


class PageTests(TestCase):
    def setUp(self):
        self.board, self.class_level, self.subject, self.chapter, self.topic = make_curriculum()

    def test_public_pages(self):
        for url in ["/", "/boards/", self.board.get_absolute_url(), self.class_level.get_absolute_url(),
                    self.subject.get_absolute_url(), self.chapter.get_absolute_url(), self.topic.get_absolute_url(),
                    "/papers/", "/previous-year-papers/", "/study-material/", "/tests/", "/tests/mock/",
                    "/scanner/", "/search/?q=quadratic", "/questions/", "/healthz/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_boards_come_from_database(self):
        self.assertContains(self.client.get("/boards/"), self.board.short_name)

    def test_friendly_404(self):
        response = self.client.get("/definitely-missing/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)

    def test_login_required_pages_redirect(self):
        for url in ["/dashboard/", "/saved/", "/assistant/", "/notifications/"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/accounts/login/", response["Location"])


class HomeHeroTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_hero_finder_counts_only_real_recent_papers(self):
        from papers.services import recent_exam_years

        board, class_level, subject, *_ = make_curriculum()
        board.state = "Delhi"
        board.save()
        years = recent_exam_years()
        make_paper(subject, years[0])
        make_paper(subject, years[1], slug="older")
        demo = make_paper(subject, years[2], slug="demo")
        demo.is_sample = True
        demo.save()
        make_paper(subject, years[0] - 10, slug="too-old")
        response = self.client.get("/")
        hero = response.context["hero"]
        self.assertEqual(hero["papers"], 2)
        self.assertEqual(hero["finder"], [{"slug": "cbse", "name": "Delhi (CBSE)", "classes": [
            {"slug": "class-10", "name": "Class 10", "count": 2}]}])
        self.assertContains(response, 'id="ph-board"')
        self.assertContains(response, 'action="/previous-year-papers/"')

    def test_hero_renders_without_any_papers(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="ph-board"')


class AccountTests(TestCase):
    def test_signup_creates_profile_and_logs_in(self):
        board, class_level, *_ = make_curriculum()
        response = self.client.post(reverse("accounts:signup"), {
            "first_name": "Priya", "email": "Priya@Example.com", "board": board.id,
            "class_level": class_level.id, "password1": "Str0ng-pass-123", "password2": "Str0ng-pass-123"})
        self.assertRedirects(response, reverse("dashboard:home"))
        from accounts.models import User

        user = User.objects.get(email="priya@example.com")
        self.assertEqual(user.profile.class_level, class_level)

    def test_login_with_email(self):
        make_user("a@example.com", "Str0ng-pass-123")
        response = self.client.post(reverse("accounts:login"), {"username": "A@example.com",
                                                                "password": "Str0ng-pass-123"})
        self.assertEqual(response.status_code, 302)

    def test_api_token_login(self):
        make_user("api@example.com", "Str0ng-pass-123")
        r = self.client.post(reverse("api:login"), {"email": "api@example.com", "password": "Str0ng-pass-123"},
                             content_type="application/json")
        token = r.json()["token"]
        me = self.client.get(reverse("api:me"), HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(me.json()["email"], "api@example.com")
        self.assertNotIn("password", str(me.json()))


class BookmarkTests(TestCase):
    def test_toggle(self):
        _, _, subject, chapter, _ = make_curriculum()
        question, _ = make_mcq(subject, chapter)
        self.client.force_login(make_user())
        url = reverse("api:bookmark-toggle")
        self.assertTrue(self.client.post(url, {"kind": "question", "object_id": question.id},
                                         content_type="application/json").json()["bookmarked"])
        self.assertEqual(Bookmark.objects.count(), 1)
        self.assertFalse(self.client.post(url, {"kind": "question", "object_id": question.id},
                                          content_type="application/json").json()["bookmarked"])
        self.assertEqual(Bookmark.objects.count(), 0)

    def test_toggle_unknown_object(self):
        self.client.force_login(make_user())
        r = self.client.post(reverse("api:bookmark-toggle"), {"kind": "question", "object_id": 999},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)


class SearchTests(TestCase):
    def test_search_groups_and_history(self):
        _, _, subject, chapter, _ = make_curriculum()
        make_mcq(subject, chapter, text="Find the discriminant of a quadratic equation")
        user = make_user()
        self.client.force_login(user)
        data = self.client.get(reverse("api:search"), {"q": "quadratic"}).json()
        keys = {g["key"] for g in data["results"]}
        self.assertIn("chapters", keys)
        self.assertIn("questions", keys)
        self.assertEqual(SearchHistory.objects.get(user=user).query, "quadratic")

    def test_filters_by_year(self):
        _, _, subject, _, _ = make_curriculum()
        make_paper(subject, 2020)
        make_paper(subject, 2023)
        data = self.client.get(reverse("api:search"), {"q": "Paper", "year": 2023, "type": "previous_year"}).json()
        titles = [i["title"] for g in data["results"] for i in g["items"]]
        self.assertEqual(titles, ["Paper 2023"])


class RecommendationTests(TestCase):
    def test_weak_chapter_gets_targeted_material_and_questions(self):
        _, _, subject, chapter, _ = make_curriculum()
        questions = [make_mcq(subject, chapter, text=f"Q{i}")[0] for i in range(3)]
        add_appearance(questions[0], make_paper(subject, 2023))
        notes = StudyMaterial.objects.create(title="Quadratic revision", slug="quad-rev", subject=subject,
                                             chapter=chapter, material_type="revision")
        user = make_user()
        test = make_test(subject, chapter, questions)
        attempt = engine.start_attempt(user, test)
        for tq in engine.ordered_test_questions(attempt):  # answer everything wrongly
            wrong = tq.question.options.filter(is_correct=False).first()
            engine.save_answer(attempt, tq.id, option_ids=[wrong.id])
        with self.captureOnCommitCallbacks(execute=True):
            engine.submit_attempt(attempt)
        recs = generate_for_user(user)
        targets = {r.content_object for r in recs}
        self.assertIn(notes, targets)
        self.assertIn(questions[0], targets)


class LaunchHardeningTests(TestCase):
    """Guards added before going live: data safety, abuse limits and crawler rules."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # rate-limit counters live in the cache
        self.addCleanup(cache.clear)

    def test_seed_reset_keeps_real_boards_and_papers(self):
        from io import StringIO

        from boards.models import Board
        from core.management.commands.seed_demo import Command
        from papers.models import QuestionPaper

        board, _, subject, _, _ = make_curriculum()
        Board.objects.filter(pk=board.pk).update(is_sample=True)  # the old, wrongly-flagged state
        paper = make_paper(subject, 2024)
        Command(stdout=StringIO())._reset()
        self.assertTrue(Board.objects.filter(pk=board.pk).exists())
        self.assertTrue(QuestionPaper.objects.filter(pk=paper.pk).exists())

    def test_failed_logins_are_rate_limited(self):
        make_user()
        url = reverse("accounts:login")
        for _ in range(10):
            self.assertEqual(self.client.post(url, {"username": "student@example.com",
                                                    "password": "wrong"}).status_code, 200)
        r = self.client.post(url, {"username": "student@example.com", "password": "Str0ng-pass-123"})
        self.assertEqual(r.status_code, 429)

    def test_successful_logins_are_not_counted(self):
        make_user()
        url = reverse("accounts:login")
        for _ in range(12):
            r = self.client.post(url, {"username": "student@example.com", "password": "Str0ng-pass-123"})
            self.assertEqual(r.status_code, 302)
            self.client.logout()

    def test_spoofed_forwarded_for_does_not_reset_limits(self):
        from django.conf import settings
        from django.test import override_settings

        # Direct connection (no proxy): a client-sent X-Forwarded-For must be ignored.
        no_proxy = override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": 0})
        no_proxy.enable()
        self.addCleanup(no_proxy.disable)
        make_user()
        url = reverse("accounts:login")
        for i in range(10):
            self.client.post(url, {"username": "student@example.com", "password": "wrong"},
                             HTTP_X_FORWARDED_FOR=f"10.0.0.{i}")
        r = self.client.post(url, {"username": "student@example.com", "password": "wrong"},
                             HTTP_X_FORWARDED_FOR="10.0.0.99")
        self.assertEqual(r.status_code, 429)

    def test_robots_txt_hides_private_pages(self):
        r = self.client.get("/robots.txt")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Disallow: /admin/", r.content.decode())

    def test_year_grid_skips_papers_without_pdf(self):
        from papers.services import year_grid

        _, _, subject, _, _ = make_curriculum()
        make_paper(subject, 2024, pdf="")
        self.assertEqual(year_grid([subject], [2024])[0]["cells"][0]["papers"], [])

    def test_single_users_search_is_not_suggested_to_others(self):
        from search.services import suggestions

        SearchHistory.objects.create(query="my private query", normalized_query="my private query")
        texts = [s["text"] for s in suggestions("my private")]
        self.assertNotIn("my private query", texts)

    def test_answers_hidden_while_question_is_in_unfinished_test(self):
        _, _, subject, chapter, _ = make_curriculum()
        question, _ = make_mcq(subject, chapter)
        test = make_test(subject, chapter, [question])
        user = make_user()
        self.client.force_login(user)
        api_url = reverse("api:question-detail", args=[question.pk])
        self.assertFalse(self.client.get(api_url).json()["answers_hidden"])

        attempt = engine.start_attempt(user, test)
        data = self.client.get(api_url).json()
        self.assertTrue(data["answers_hidden"])
        self.assertTrue(all(o["is_correct"] is None for o in data["options"]))
        self.assertNotContains(self.client.get(question.get_absolute_url()), "data-correct=")

        engine.submit_attempt(attempt)
        self.assertFalse(self.client.get(api_url).json()["answers_hidden"])
        self.assertContains(self.client.get(question.get_absolute_url()), "data-correct=")
