"""
Load clearly-labelled sample data for local development.

    python manage.py seed_demo            # create/update demo content
    python manage.py seed_demo --reset    # delete existing sample content first
    python manage.py seed_demo --no-student

All created content has is_sample=True and shows a "Sample" badge in the UI.
Demo "previous-year" papers are NOT official papers.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.text import slugify

from boards.models import Board, Chapter, ClassLevel, Subject, Topic
from content.models import StudyMaterial
from core import demo_data as D
from notifications.models import Announcement
from papers.models import QuestionPaper
from questions.models import Concept, Question, QuestionAppearance, QuestionOption
from testengine.models import Test, TestQuestion

DEMO_EMAIL = "student@prepai.local"
DEMO_PASSWORD = "demo-student-2026"

PDF_CHAR_MAP = str.maketrans({
    "²": "^2", "³": "^3", "⁵": "^5", "⁻": "-", "¹": "1", "√": "sqrt", "→": "->", "−": "-", "×": "x",
    "θ": "theta", "Ω": " ohm", "°": " deg", "—": "-", "–": "-", "₀": "0", "₁": "1", "₂": "2", "₃": "3",
    "₄": "4", "₆": "6", "“": '"', "”": '"', "’": "'", "±": "+/-", "≠": "!=",
})


def make_pdf(title, lines):
    """Build a small, valid multi-page PDF (Helvetica, WinAnsi) — no dependencies."""
    def esc(text):
        text = text.translate(PDF_CHAR_MAP).encode("latin-1", "replace").decode("latin-1")
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    wrapped = []
    for line in lines:
        line = line or " "
        while len(line) > 88:
            cut = line.rfind(" ", 0, 88)
            cut = cut if cut > 20 else 88
            wrapped.append(line[:cut])
            line = "   " + line[cut:].lstrip()
        wrapped.append(line)
    per_page = 46
    pages = [wrapped[i:i + per_page] for i in range(0, max(len(wrapped), 1), per_page)] or [[]]

    objects = []  # index 0 -> object 1

    def add(body):
        objects.append(body)
        return len(objects)

    catalog = add(None)
    pages_obj = add(None)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    bold = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    page_ids = []
    for number, page_lines in enumerate(pages, start=1):
        ops = ["BT", "/F2 15 Tf", "50 800 Td", f"({esc(title)}) Tj", "/F1 8 Tf", "0 -16 Td",
               f"(SAMPLE / DEMO CONTENT - not an official board paper - page {number} of {len(pages)}) Tj",
               "/F1 11 Tf", "0 -26 Td", "15 TL"]
        ops += [f"({esc(line)}) '" for line in page_lines]
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(add(
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font} 0 R /F2 {bold} 0 R >> >> /Contents {content} 0 R >>".encode()))
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode()
    objects[pages_obj - 1] = (f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] "
                              f"/Count {len(page_ids)} >>").encode()

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class Command(BaseCommand):
    help = "Load clearly-labelled sample data (boards, content, tests, demo papers, demo student)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing sample content first.")
        parser.add_argument("--no-student", action="store_true", help="Skip creating the demo student.")

    def handle(self, *args, **options):
        from notifications import signals as notif_signals

        # Don't spam notifications while bulk-loading content.
        post_save.disconnect(notif_signals.material_published, sender=StudyMaterial)
        post_save.disconnect(notif_signals.paper_published, sender=QuestionPaper)
        try:
            with transaction.atomic():
                if options["reset"]:
                    self._reset()
                self._boards()
                self._questions()
                self._papers()
                self._materials()
                self._tests()
                Announcement.objects.get_or_create(
                    title="Welcome to PrepAI (demo)",
                    defaults={"message": "This is a development environment with sample content.",
                              "url": "/boards/", "is_published": True})
        finally:
            post_save.connect(notif_signals.material_published, sender=StudyMaterial)
            post_save.connect(notif_signals.paper_published, sender=QuestionPaper)
        if not options["no_student"]:
            self._student()
        cache.clear()
        self.stdout.write(self.style.SUCCESS("Sample data loaded."))
        if not options["no_student"]:
            self.stdout.write(f"Demo student: {DEMO_EMAIL} / {DEMO_PASSWORD}")

    # ------------------------------------------------------------------
    def _reset(self):
        for model in (Test, QuestionPaper, StudyMaterial, Question):
            model.objects.filter(is_sample=True).delete()
        Board.objects.filter(is_sample=True).delete()
        self.stdout.write("Removed existing sample content.")

    def _boards(self):
        self.subjects, self.chapters, self.topics, self.classes = {}, {}, {}, {}
        for short, name, btype, state, featured, order in D.BOARDS:
            board, _ = Board.objects.update_or_create(
                slug=slugify(short), defaults=dict(name=name, short_name=short, board_type=btype, state=state,
                                                   is_featured=featured, order=order, is_sample=True))
            for number, subjects in D.CURRICULUM.get(short, {}).items():
                cl, _ = ClassLevel.objects.update_or_create(
                    board=board, slug=f"class-{number}",
                    defaults=dict(name=f"Class {number}", number=number, order=number, is_sample=True))
                self.classes[(short, number)] = cl
                for s_order, (s_name, meta) in enumerate(subjects.items()):
                    subject, _ = Subject.objects.update_or_create(
                        class_level=cl, slug=slugify(s_name),
                        defaults=dict(name=s_name, icon=meta["icon"], color=meta["color"],
                                      is_popular=meta["popular"], order=s_order, is_sample=True))
                    self.subjects[(short, number, s_name)] = subject
                    for c_order, (c_name, topics) in enumerate(meta["chapters"].items(), start=1):
                        chapter, _ = Chapter.objects.update_or_create(
                            subject=subject, slug=slugify(c_name),
                            defaults=dict(name=c_name, number=c_order, order=c_order, is_sample=True))
                        self.chapters[(short, number, s_name, c_name)] = chapter
                        for t_order, t_name in enumerate(topics):
                            topic, _ = Topic.objects.update_or_create(
                                chapter=chapter, slug=slugify(t_name),
                                defaults=dict(name=t_name, order=t_order, is_sample=True))
                            self.topics[(short, number, s_name, c_name, t_name)] = topic
        self.concepts = {}
        for scope, names in D.CONCEPTS.items():
            for name in names:
                concept, _ = Concept.objects.get_or_create(subject=self.subjects[scope], slug=slugify(name),
                                                           defaults={"name": name})
                self.concepts[(scope, name)] = concept

    def _questions(self):
        self.questions = {}
        for data in D.QUESTIONS:
            scope = data["scope"]
            subject = self.subjects[scope]
            chapter = self.chapters[(*scope, data["chapter"])]
            topic = self.topics.get((*scope, data["chapter"], data.get("topic")))
            question = Question.objects.filter(subject=subject, text=data["text"]).first() or Question(subject=subject)
            question.chapter, question.topic = chapter, topic
            question.question_type = data["type"]
            question.text = data["text"]
            question.difficulty = data["difficulty"]
            question.marks = Decimal(data["marks"])
            question.answer = data.get("answer", "")
            question.explanation = data.get("explanation", "")
            question.is_important = data.get("important", False)
            question.is_sample = True
            question.save()
            question.options.all().delete()
            QuestionOption.objects.bulk_create([
                QuestionOption(question=question, text=text, is_correct=correct, order=i)
                for i, (text, correct) in enumerate(data.get("options", []))
            ])
            question.concepts.set([self.concepts[(scope, c)] for c in data.get("concepts", [])])
            self.questions[data["key"]] = question

    def _paper(self, key, scope, paper_type, title, year=None, chapter=None, question_keys=()):
        subject = self.subjects[scope]
        slug = slugify(title)[:250]
        paper, _ = QuestionPaper.objects.update_or_create(slug=slug, defaults=dict(
            title=title, subject=subject, paper_type=paper_type, year=year, chapter=chapter,
            exam_type="annual", total_marks=80, duration_minutes=180, is_sample=True,
            description="Demo paper generated for development and testing. It is NOT an official "
                        "board examination paper; years exist only to demonstrate frequency analysis.",
        ))
        lines = [f"{subject.class_level.board.name} - {subject.class_level.name} - {subject.name}", "",
                 "General instructions: All questions are compulsory. This is sample content.", ""]
        for i, qkey in enumerate(question_keys, start=1):
            q = self.questions[qkey]
            lines.append(f"Q{i}. {q.text}  [{q.marks.normalize()} mark(s)]")
            for letter, option in zip("abcd", q.options.all()):
                lines.append(f"     ({letter}) {option.text}")
            lines.append("")
        if not paper.pdf:
            paper.pdf.save(f"{slug[:60]}.pdf", ContentFile(make_pdf(title, lines)), save=True)
        return paper

    def _papers(self):
        self.papers = {}
        for key, scope, year, items in D.DEMO_PYP:
            subject_name = scope[2]
            title = f"[Demo] {scope[0]} Class {scope[1]} {subject_name} — {year} (sample previous-year format)"
            paper = self._paper(key, scope, "previous_year", title, year=year,
                                question_keys=[qk for qk, _n, _m in items])
            for qkey, number, marks in items:
                QuestionAppearance.objects.update_or_create(
                    question=self.questions[qkey], paper=paper,
                    defaults=dict(year=year, question_number=number, marks=Decimal(marks)))
            self.papers[key] = paper
        for key, scope, ptype, chapter_name, title, qkeys in D.OTHER_PAPERS:
            chapter = self.chapters.get((*scope, chapter_name)) if chapter_name else None
            self.papers[key] = self._paper(key, scope, ptype, title, year=2026, chapter=chapter, question_keys=qkeys)

    def _materials(self):
        for scope, chapter_name, topic_name, mtype, title, summary, body, featured in D.MATERIALS:
            StudyMaterial.objects.update_or_create(slug=slugify(title), defaults=dict(
                title=title, subject=self.subjects[scope], material_type=mtype,
                chapter=self.chapters.get((*scope, chapter_name)),
                topic=self.topics.get((*scope, chapter_name, topic_name)),
                summary=summary, body=body, is_featured=featured, is_sample=True,
                reading_minutes=max(2, len(body.split()) // 180 + 1)))
        subject = self.subjects[("CBSE", 10, "Science")]
        pdf_material, created = StudyMaterial.objects.update_or_create(
            slug="class-10-science-sample-notes-pdf", defaults=dict(
                title="Class 10 Science — Sample Notes (PDF)", subject=subject, material_type="pdf",
                summary="A downloadable PDF of quick notes (demo).", is_sample=True))
        if not pdf_material.file:
            pdf_material.file.save("class-10-science-notes.pdf", ContentFile(make_pdf(
                "Class 10 Science - Sample Notes", [
                    "Electricity: V = IR. Series: R = R1 + R2. Parallel: 1/R = 1/R1 + 1/R2.",
                    "Light: power of a lens P = 1/f (f in metres), unit dioptre.",
                    "Chemical reactions: combination, decomposition, displacement, double displacement.",
                    "Life processes: photosynthesis 6CO2 + 6H2O -> C6H12O6 + 6O2.",
                ])), save=True)

    def _tests(self):
        for key, title, ttype, scope, chapter_name, duration, qkeys, extra in D.TESTS:
            board, number, subject_name = scope
            test, _ = Test.objects.update_or_create(slug=slugify(title), defaults=dict(
                title=title, test_type=ttype, duration_minutes=duration, is_sample=True,
                board=self.classes[(board, number)].board, class_level=self.classes[(board, number)],
                subject=self.subjects.get(scope) if subject_name else None,
                chapter=self.chapters.get((*scope, chapter_name)) if chapter_name else None,
                is_featured=extra.get("is_featured", False),
                description=f"Sample {dict(Test.TestType.choices)[ttype].lower()} with {len(qkeys)} questions.",
            ))
            self._assign(test, qkeys, extra.get("negative"))
        # A previous-year test built from the 2023 demo maths paper.
        paper = self.papers["m2023"]
        test, _ = Test.objects.update_or_create(slug="demo-2023-maths-previous-year-test", defaults=dict(
            title="[Demo] 2023 Mathematics — Previous Year Test", test_type="previous_year", paper=paper,
            subject=paper.subject, class_level=paper.subject.class_level, board=paper.subject.class_level.board,
            duration_minutes=20, is_sample=True, description="Attempt the questions from the demo 2023 paper."))
        self._assign(test, [qk for qk, _n, _m in dict((k, i) for k, _s, _y, i in D.DEMO_PYP)["m2023"]], None)

    def _assign(self, test, qkeys, negative):
        test.test_questions.all().delete()
        TestQuestion.objects.bulk_create([
            TestQuestion(test=test, question=self.questions[qk], order=i,
                         negative_marks=Decimal(negative) if negative and self.questions[qk].is_objective else None)
            for i, qk in enumerate(qkeys, start=1)
        ])

    def _student(self):
        """Demo student with a couple of finished attempts so the dashboard has data."""
        from testengine import services as engine

        User = get_user_model()
        user = User.objects.filter(email=DEMO_EMAIL).first()
        if user is None:
            user = User.objects.create_user(email=DEMO_EMAIL, password=DEMO_PASSWORD, first_name="Aarav",
                                            last_name="(Demo)")
        profile = user.profile
        profile.board = self.classes[("CBSE", 10)].board
        profile.class_level = self.classes[("CBSE", 10)]
        profile.exam_date = timezone.localdate() + timedelta(days=150)
        profile.save()
        profile.subjects.set([self.subjects[("CBSE", 10, "Mathematics")], self.subjects[("CBSE", 10, "Science")]])
        if user.test_attempts.exists():
            return

        # answers: question key -> option index / text. Some deliberately wrong.
        plans = [
            ("quadratic-equations-chapter-test", {"roots_2x2": 0, "discriminant": 1, "larger_root": "3",
                                                  "distinct_roots": 0, "consecutive": "13 and 14"}),
            ("electricity-chapter-test", {"ohm": 0, "current": "0.5", "series": 0, "coulomb": 0}),
            ("trigonometry-practice-test", {"sinA": 1, "sin2cos2": 0, "tan45": 2}),
        ]
        for slug, answers in plans:
            test = Test.objects.get(slug=slug)
            attempt = engine.start_attempt(user, test)
            for tq in engine.ordered_test_questions(attempt):
                key = next((k for k, q in self.questions.items() if q.pk == tq.question_id), None)
                if key not in answers:
                    continue
                choice = answers[key]
                if isinstance(choice, int):
                    engine.save_answer(attempt, tq.id, option_ids=[list(tq.question.options.all())[choice].id],
                                       time_spent_seconds=40)
                else:
                    engine.save_answer(attempt, tq.id, text_answer=choice, time_spent_seconds=60)
            engine.submit_attempt(attempt)
