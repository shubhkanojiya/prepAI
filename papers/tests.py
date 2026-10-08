"""Previous-year archive grid and the bulk import command."""
import shutil
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from boards.models import Subject
from core.testing import add_appearance, make_curriculum, make_mcq, make_paper
from papers.management.commands.fetch_cbse_papers import match_subject, pick_set
from papers.management.commands.import_papers import parse_filename
from papers.models import QuestionPaper
from papers.services import recent_exam_years, year_grid

PDF = b"%PDF-1.4\n%%EOF"


class ArchiveTests(TestCase):
    def setUp(self):
        self.board, self.class_level, self.subject, self.chapter, _ = make_curriculum()

    def test_recent_exam_years_roll_over_after_results(self):
        self.assertEqual(recent_exam_years(today=date(2026, 3, 1)), [2025, 2024, 2023, 2022, 2021])
        self.assertEqual(recent_exam_years(today=date(2026, 9, 1)), [2026, 2025, 2024, 2023, 2022])

    def test_year_grid_places_papers_and_orders_exams(self):
        years = [2025, 2024, 2023]
        supp = make_paper(self.subject, 2024, slug="supp-2024")
        supp.exam_type = "supplementary"
        supp.save()
        main = make_paper(self.subject, 2024)
        make_paper(self.subject, 2025, paper_type="sample")  # not a previous-year paper
        row = year_grid([self.subject], years)[0]
        self.assertEqual([c["year"] for c in row["cells"]], years)
        self.assertEqual(row["cells"][1]["papers"], [main, supp])
        self.assertEqual(row["cells"][0]["papers"], [])
        self.assertEqual(row["available"], 1)

    def test_year_grid_hides_demo_paper_once_real_one_exists(self):
        demo = make_paper(self.subject, 2024, slug="demo-2024")
        QuestionPaper.objects.filter(pk=demo.pk).update(is_sample=True)
        self.assertEqual(year_grid([self.subject], [2024])[0]["cells"][0]["papers"], [demo])
        real = make_paper(self.subject, 2024)
        self.assertEqual(year_grid([self.subject], [2024])[0]["cells"][0]["papers"], [real])

    def test_archive_page_shows_selected_board_and_class(self):
        year = recent_exam_years()[0]
        paper = make_paper(self.subject, year)
        response = self.client.get("/previous-year-papers/", {"board": "cbse", "class": "class-10"})
        self.assertContains(response, paper.get_absolute_url())
        self.assertContains(response, "1 of 5 subject-years available")

    def test_archive_filters_by_subject_year_and_exam(self):
        years = recent_exam_years()
        other = Subject.objects.create(class_level=self.class_level, name="Science", slug="science")
        make_paper(self.subject, years[0])
        supp = make_paper(self.subject, years[1], slug="supp")
        QuestionPaper.objects.filter(pk=supp.pk).update(exam_type="supplementary")
        url = "/previous-year-papers/"
        base = {"board": self.board.id, "class_level": "class-10"}
        response = self.client.get(url, {**base, "subject": self.subject.id})
        self.assertEqual([r["subject"] for r in response.context["rows"]], [self.subject])
        self.assertNotContains(response, other.get_absolute_url())
        response = self.client.get(url, {**base, "year": years[1]})
        self.assertEqual(response.context["years"], [years[1]])
        self.assertEqual(response.context["available"], 1)
        response = self.client.get(url, {**base, "exam_type": "supplementary"})
        self.assertEqual(response.context["available"], 1)
        self.assertEqual(response.context["rows"][0]["cells"][1]["papers"], [supp])

    def test_archive_chapter_filter_lists_questions_asked(self):
        year = recent_exam_years()[0]
        paper = make_paper(self.subject, year)
        question, _ = make_mcq(self.subject, self.chapter, text="Find the discriminant")
        add_appearance(question, paper, "7")
        response = self.client.get("/previous-year-papers/", {
            "board": "cbse", "class_level": "class-10", "subject": self.subject.id, "chapter": self.chapter.id})
        self.assertContains(response, "Quadratic Equations in previous papers")
        self.assertContains(response, "Find the discriminant")
        self.assertContains(response, paper.get_absolute_url())

    def test_paper_list_chapter_filter_matches_tagged_questions(self):
        paper = make_paper(self.subject, 2024)
        make_paper(self.subject, 2023)
        question, _ = make_mcq(self.subject, self.chapter)
        add_appearance(question, paper)
        response = self.client.get("/previous-year-papers/all/", {
            "board": self.board.id, "class_level": self.class_level.id, "subject": self.subject.id,
            "chapter": self.chapter.id})
        self.assertEqual(list(response.context["page_obj"]), [paper])

    def test_subject_page_has_year_strip(self):
        make_paper(self.subject, recent_exam_years()[1])
        response = self.client.get(self.subject.get_absolute_url())
        self.assertContains(response, "pyp-year available")


class ImportCommandTests(TestCase):
    def setUp(self):
        self.board, self.class_level, self.subject, *_ = make_curriculum()
        self.root = Path(tempfile.mkdtemp())
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(shutil.rmtree, self.media, True)

    def _file(self, rel, content=PDF):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def _run(self, *args):
        with override_settings(MEDIA_ROOT=self.media):
            call_command("import_papers", str(self.root), *args, stdout=StringIO(), stderr=StringIO())

    def test_parse_filename(self):
        self.assertEqual(parse_filename("2024"), (2024, "annual", False))
        self.assertEqual(parse_filename("2024-supplementary-solutions"), (2024, "supplementary", True))
        self.assertEqual(parse_filename("2023_Term-1"), (2023, "term_1", False))
        self.assertIsNone(parse_filename("notes"))
        self.assertIsNone(parse_filename("2024-random"))

    def test_imports_papers_and_solutions_idempotently(self):
        self._file("CBSE/10/Mathematics/2025.pdf")
        self._file("cbse/class-10/mathematics/2025-solutions.pdf")
        self._file("cbse/10/mathematics/2024-supp.pdf")
        self._file("cbse/10/mathematics/2023.pdf", b"not a pdf")
        self._file("unknown-board/10/maths/2025.pdf")
        self._run()
        self._run()
        papers = QuestionPaper.objects.filter(subject=self.subject).order_by("-year")
        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0].paper_type, "previous_year")
        self.assertTrue(papers[0].pdf and papers[0].solution_pdf)
        self.assertEqual(papers[1].exam_type, "supplementary")
        self.assertIn("CBSE Class 10 Mathematics 2025", papers[0].title)

    def test_model_papers_import_separately(self):
        self._file("cbse/10/mathematics/2025.pdf")
        self._run()
        self._run("--paper-type", "model")
        model = QuestionPaper.objects.get(paper_type="model")
        self.assertIn("Model Paper", model.title)
        self.assertIn("Not an actual board examination paper", model.description)
        self.assertEqual(QuestionPaper.objects.filter(paper_type="previous_year").count(), 1)

    def test_board_option_limits_import(self):
        self._file("cbse/10/mathematics/2025.pdf")
        self._file("icse/10/mathematics/2025.pdf")
        self._run("--board", "icse")
        self.assertFalse(QuestionPaper.objects.exists())
        self._run("--board", "CBSE")
        self.assertEqual(QuestionPaper.objects.count(), 1)

    def test_dry_run_changes_nothing(self):
        self._file("cbse/10/mathematics/2025.pdf")
        self._run("--dry-run")
        self.assertFalse(QuestionPaper.objects.exists())

    def test_real_import_ignores_demo_paper_for_same_year(self):
        demo = make_paper(self.subject, 2025, slug="demo-2025")
        QuestionPaper.objects.filter(pk=demo.pk).update(is_sample=True)
        self._file("cbse/10/mathematics/2025.pdf")
        self._run()
        self.assertEqual(QuestionPaper.objects.filter(subject=self.subject, year=2025, is_sample=False).count(), 1)


class CbseFetchTests(TestCase):
    def test_match_subject_handles_cbse_file_names(self):
        cases = {(10, "Math_S.zip"): "mathematics", (10, "241_Mathematics_Basic.zip"): "mathematics-basic",
                 (10, "Scince.zip"): "science", (10, "SST.zip"): "social-science",
                 (10, "English_&_Lit.zip"): "english", (10, "English_Communicative.zip"): None,
                 (10, "Hindi_Coursse_B.zip"): "hindi-course-b", (10, "Home_Science.zip"): None,
                 (12, "BS.zip"): "business-studies", (12, "Poltical_Science.zip"): "political-science",
                 (12, "Applied_Math.zip"): "applied-mathematics", (12, "MATHS.zip"): "mathematics"}
        for (cls, name), slug in cases.items():
            self.assertEqual(match_subject(cls, name), slug, name)

    def test_pick_set_prefers_first_set_and_skips_visually_impaired(self):
        names = ["041/30 B_Maths Std for Visually Impaired.pdf", "041/30-2-1_Maths.pdf",
                 "041/30-1-2_Maths.pdf", "041/30-1-1_Maths.pdf", "041/"]
        self.assertEqual(pick_set(names, "mathematics"), "041/30-1-1_Maths.pdf")
        self.assertEqual(pick_set(["a/Set 2.pdf", "a/Set 10.pdf"], "physics"), "a/Set 2.pdf")
        self.assertIsNone(pick_set(["a/readme.txt"], "physics"))
