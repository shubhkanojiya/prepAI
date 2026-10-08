"""Boards that hold real classes are real content, not demo data.

seed_demo used to flag the shared boards (cbse, icse, …) as samples, which made
`seed_demo --reset` cascade-delete every real class, subject and paper.
"""
from django.db import migrations


def unflag_real_boards(apps, schema_editor):
    Board = apps.get_model("boards", "Board")
    Board.objects.filter(is_sample=True, classes__is_sample=False).update(is_sample=False)


class Migration(migrations.Migration):

    dependencies = [
        ("boards", "0002_subject_default_colour"),
    ]

    operations = [
        migrations.RunPython(unflag_real_boards, migrations.RunPython.noop),
    ]
