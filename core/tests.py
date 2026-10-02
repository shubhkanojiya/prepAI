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
