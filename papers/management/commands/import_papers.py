"""
Bulk-import previous-year papers from a folder of PDFs.

Folder layout (names match a slug, short name/name, or class number):

    <root>/<board>/<class>/<subject>/<year>[-<exam>][-solutions].pdf

    papers_import/cbse/10/mathematics/2025.pdf
    papers_import/cbse/10/mathematics/2025-solutions.pdf
    papers_import/cbse/class-12/physics/2024-supplementary.pdf
    papers_import/MSBSHSE/Class 10/Science and Technology Part 1/2023.pdf

<exam> is one of: annual/main, supplementary/supp/compartment, term-1, term-2, pre-board, other.
Re-running is safe: a paper is identified by subject + year + exam, so files are updated
in place (existing PDFs are kept unless --replace is given).
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.signals import post_save
from django.test.utils import override_settings
from django.utils.text import slugify

from boards.models import Board, ClassLevel, Subject
from core.validators import validate_pdf
from papers.models import QuestionPaper

EXAM_ALIASES = {
    "annual": "annual", "main": "annual",
    "supplementary": "supplementary", "supp": "supplementary", "compartment": "supplementary",
    "term1": "term_1", "term2": "term_2",
    "preboard": "pre_board",
    "other": "other",
}
SOLUTION_WORDS = {"solution", "solutions", "answers", "answer", "markingscheme", "ms"}
FILENAME_RE = re.compile(r"^(?P<year>(19|20)\d{2})(?P<rest>.*)$")


def _key(text):
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def parse_filename(stem):
    """'2024-supplementary-solutions' → (2024, 'supplementary', True). None if not a paper."""
    match = FILENAME_RE.match(stem.strip())
    if not match:
        return None
    rest = _key(match["rest"])
    is_solution = False
    for word in sorted(SOLUTION_WORDS, key=len, reverse=True):
        if rest.endswith(word):
            is_solution, rest = True, rest[: -len(word)]
            break
    if rest and rest not in EXAM_ALIASES:
        return None
    return int(match["year"]), EXAM_ALIASES.get(rest, "annual"), is_solution


class Command(BaseCommand):
    help = "Bulk-import previous-year papers from <root>/<board>/<class>/<subject>/<year>.pdf"

    def add_arguments(self, parser):
        parser.add_argument("root", help="Folder containing one sub-folder per board")
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen; change nothing.")
        parser.add_argument("--replace", action="store_true", help="Overwrite PDFs that are already attached.")
        parser.add_argument("--unpublished", action="store_true",
                            help="Create new papers unpublished (review them in admin first).")
        parser.add_argument("--board", action="append", dest="only_boards", metavar="FOLDER",
                            help="Only import this board folder (repeatable). Default: every folder.")
        parser.add_argument("--max-mb", type=int,
                            help="Allow PDFs up to this size for this import (default: MAX_PDF_UPLOAD_MB).")
        parser.add_argument("--paper-type", default=QuestionPaper.PaperType.PREVIOUS_YEAR,
                            choices=[QuestionPaper.PaperType.PREVIOUS_YEAR, QuestionPaper.PaperType.MODEL],
                            help="Import as previous-year papers (default) or as the board's model papers.")
        parser.add_argument("--notify", action="store_true",
                            help="Send 'new paper' notifications to students (off by default).")

    def handle(self, *args, **options):
        root = Path(options["root"]).expanduser()
        if not root.is_dir():
            raise CommandError(f"Folder not found: {root}")
        self.options = options
        self.stats = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}

        from notifications import signals as notif_signals
        if not options["notify"]:
            post_save.disconnect(notif_signals.paper_published, sender=QuestionPaper)
        try:
            only = {_key(b) for b in options["only_boards"] or []}
            for board_dir in sorted(p for p in root.iterdir() if p.is_dir()):
                if not only or _key(board_dir.name) in only:
                    self._import_board(board_dir)
        finally:
            if not options["notify"]:
                post_save.connect(notif_signals.paper_published, sender=QuestionPaper)

        prefix = "[dry run] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            prefix + ", ".join(f"{count} {label}" for label, count in self.stats.items())))

    # --- folder matching -------------------------------------------------------------------

    def _skip(self, path, reason):
        self.stats["skipped"] += 1
        self.stderr.write(self.style.WARNING(f"skip {path}: {reason}"))

    def _import_board(self, board_dir):
        wanted = _key(board_dir.name)
        board = next((b for b in Board.objects.all()
                      if wanted in {_key(b.slug), _key(b.short_name), _key(b.name)}), None)
        if not board:
            return self._skip(board_dir, "no board with this slug or name")
        for class_dir in sorted(p for p in board_dir.iterdir() if p.is_dir()):
            self._import_class(board, class_dir)

    def _import_class(self, board, class_dir):
        wanted = _key(class_dir.name)
        digits = re.sub(r"\D", "", class_dir.name)
        class_level = next((c for c in ClassLevel.objects.filter(board=board)
                            if wanted in {_key(c.slug), _key(c.name)}
                            or (digits and int(digits) == c.number)), None)
        if not class_level:
            return self._skip(class_dir, f"no class like this in {board}")
        for subject_dir in sorted(p for p in class_dir.iterdir() if p.is_dir()):
            wanted = _key(subject_dir.name)
            subject = next((s for s in Subject.objects.filter(class_level=class_level)
                            if wanted in {_key(s.slug), _key(s.name), _key(s.code)} - {""}), None)
            if not subject:
                self._skip(subject_dir, f"no subject like this in {class_level}")
                continue
            for pdf_path in sorted(p for p in subject_dir.iterdir()
                                   if p.is_file() and p.suffix.lower() == ".pdf"):
                self._import_file(subject, pdf_path)

    # --- one file --------------------------------------------------------------------------

    def _import_file(self, subject, path):
        parsed = parse_filename(path.stem)
        if not parsed:
            return self._skip(path, "name must look like 2024.pdf, 2024-supplementary.pdf or 2024-solutions.pdf")
        year, exam_type, is_solution = parsed
        field_name = "solution_pdf" if is_solution else "pdf"

        paper = QuestionPaper.objects.filter(
            subject=subject, paper_type=self.options["paper_type"],
            year=year, exam_type=exam_type, is_sample=False).first()
        created = paper is None
        if created:
            paper = self._new_paper(subject, year, exam_type)
        field = getattr(paper, field_name)
        if field and not self.options["replace"]:
            self.stats["unchanged"] += 1
            return

        label = f"{'create' if created else 'update'} {paper.title} [{field_name}] <- {path.name}"
        if self.options["dry_run"]:
            self.stats["created" if created else "updated"] += 1
            self.stdout.write(label)
            return

        with path.open("rb") as handle:
            upload = File(handle, name=path.name)
            try:
                with override_settings(MAX_PDF_UPLOAD_MB=self.options["max_mb"] or settings.MAX_PDF_UPLOAD_MB):
                    validate_pdf(upload)
            except ValidationError as exc:
                return self._skip(path, " ".join(exc.messages))
            with transaction.atomic():
                if created:
                    paper.save()
                getattr(paper, field_name).save(f"{paper.slug}{'-solutions' if is_solution else ''}.pdf",
                                                upload, save=True)
        self.stats["created" if created else "updated"] += 1
        self.stdout.write(label)

    def _new_paper(self, subject, year, exam_type):
        class_level = subject.class_level
        board = class_level.board
        is_model = self.options["paper_type"] == QuestionPaper.PaperType.MODEL
        title = f"{board.short_name} {class_level.name} {subject.name} {year} {'Model Paper' if is_model else 'Question Paper'}"
        if exam_type != QuestionPaper.ExamType.ANNUAL:
            title += f" ({QuestionPaper.ExamType(exam_type).label})"
        base = slugify(title)[:270]
        slug, n = base, 2
        while QuestionPaper.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        return QuestionPaper(
            title=title, slug=slug, subject=subject, year=year, exam_type=exam_type,
            paper_type=self.options["paper_type"],
            is_published=not self.options["unpublished"],
            description=(f"Official model paper published by {board.name} for the {year} {class_level.name} "
                         f"{subject.name} examination. Not an actual board examination paper." if is_model else
                         f"{board.name} {class_level.name} {subject.name} board examination, {year}."),
        )
