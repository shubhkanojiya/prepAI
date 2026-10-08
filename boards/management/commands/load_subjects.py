"""
Create the board-exam classes and subjects listed in boards/catalog.py.

Safe to re-run: existing classes/subjects (matched by slug) keep their admin edits; only
missing ones are created. Matching demo subjects are marked as real (is_sample=False).
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from boards.catalog import CATALOG, CLASS_NAMES, POPULAR, style_for
from boards.models import Board, ClassLevel, Subject


class Command(BaseCommand):
    help = "Create the classes and subjects listed in boards/catalog.py"

    def add_arguments(self, parser):
        parser.add_argument("boards", nargs="*", help="Board short names (default: all in the catalog)")

    def handle(self, *args, **options):
        wanted = {b.casefold() for b in options["boards"]}
        created = {"classes": 0, "subjects": 0}
        for short_name, classes in CATALOG.items():
            if wanted and short_name.casefold() not in wanted:
                continue
            board = Board.objects.filter(short_name__iexact=short_name).first()
            if not board:
                self.stderr.write(self.style.WARNING(f"skip {short_name}: board not found"))
                continue
            if board.is_sample:
                Board.objects.filter(pk=board.pk).update(is_sample=False)
            for number, subjects in classes.items():
                name = CLASS_NAMES.get(number, f"Class {number}")
                class_level, new = ClassLevel.objects.get_or_create(
                    board=board, slug=slugify(name),
                    defaults={"name": name, "number": number, "order": number})
                created["classes"] += new
                if class_level.is_sample:
                    ClassLevel.objects.filter(pk=class_level.pk).update(is_sample=False)
                for order, (subject_name, code) in enumerate(subjects, start=1):
                    icon, color = style_for(subject_name)
                    subject, new = Subject.objects.get_or_create(
                        class_level=class_level, slug=slugify(subject_name),
                        defaults={"name": subject_name, "code": code, "icon": icon, "color": color,
                                  "order": order, "is_popular": subject_name.casefold() in POPULAR})
                    created["subjects"] += new
                    if not new and (subject.is_sample or not subject.code):
                        Subject.objects.filter(pk=subject.pk).update(
                            is_sample=False, code=subject.code or code)
        self.stdout.write(self.style.SUCCESS(
            f"{created['classes']} classes and {created['subjects']} subjects created"))
