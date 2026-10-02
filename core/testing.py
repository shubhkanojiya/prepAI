"""Small factory helpers shared by the test suites."""
from decimal import Decimal

from django.contrib.auth import get_user_model

from boards.models import Board, Chapter, ClassLevel, Subject, Topic
from papers.models import QuestionPaper
from questions.models import Concept, Question, QuestionAppearance, QuestionOption
from testengine.models import Test, TestQuestion


def make_curriculum(board_slug="cbse"):
    board = Board.objects.create(name=f"Board {board_slug}", short_name=board_slug.upper(), slug=board_slug)
    class_level = ClassLevel.objects.create(board=board, name="Class 10", number=10, slug="class-10")
    subject = Subject.objects.create(class_level=class_level, name="Mathematics", slug="mathematics")
    chapter = Chapter.objects.create(subject=subject, name="Quadratic Equations", slug="quadratic-equations")
    topic = Topic.objects.create(chapter=chapter, name="Nature of Roots", slug="nature-of-roots")
    return board, class_level, subject, chapter, topic


def make_mcq(subject, chapter, text="What is 2 + 2?", correct="4", wrong=("3", "5"), marks=1, qtype="mcq"):
    question = Question.objects.create(subject=subject, chapter=chapter, text=text, question_type=qtype,
                                       marks=Decimal(marks))
    options = [QuestionOption.objects.create(question=question, text=correct, is_correct=True, order=0)]
    for i, w in enumerate(wrong, start=1):
        options.append(QuestionOption.objects.create(question=question, text=w, is_correct=False, order=i))
    return question, options


def make_test(subject, chapter, questions, duration=10, negative=None, **kwargs):
    test = Test.objects.create(title=kwargs.pop("title", "Sample test"), slug=kwargs.pop("slug", "sample-test"),
                               subject=subject, chapter=chapter, duration_minutes=duration, **kwargs)
    for i, q in enumerate(questions, start=1):
        TestQuestion.objects.create(test=test, question=q, order=i,
                                    negative_marks=Decimal(negative) if negative else None)
    return test


def make_user(email="student@example.com", password="Str0ng-pass-123", **extra):
    return get_user_model().objects.create_user(email=email, password=password, **extra)


def make_paper(subject, year, slug=None, paper_type="previous_year"):
    return QuestionPaper.objects.create(title=f"Paper {year}", slug=slug or f"paper-{year}", subject=subject,
                                        year=year, paper_type=paper_type)


def add_appearance(question, paper, number="1"):
    return QuestionAppearance.objects.create(question=question, paper=paper, year=paper.year,
                                             question_number=number)


def make_concept(subject, name):
    from django.utils.text import slugify

    return Concept.objects.create(subject=subject, name=name, slug=slugify(name))
