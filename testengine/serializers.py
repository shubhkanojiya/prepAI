from rest_framework import serializers

from .models import Test, TestAttempt


class TestSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Test
        fields = ["id", "title", "slug", "description", "instructions", "test_type",
                  "difficulty", "board", "class_level", "subject", "subject_name", "chapter",
                  "duration_minutes", "pass_percentage", "max_attempts", "question_count",
                  "is_sample", "url"]


class AttemptSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source="test.title", read_only=True)
    remaining_seconds = serializers.IntegerField(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = TestAttempt
        fields = ["id", "test", "test_title", "status", "started_at", "deadline", "submitted_at",
                  "remaining_seconds", "time_taken_seconds", "score", "max_score", "percentage",
                  "accuracy", "correct_count", "incorrect_count", "unanswered_count",
                  "ungraded_count", "url"]
        read_only_fields = fields


def attempt_question_payload(attempt, test_questions, answers):
    """
    Data needed by the test interface. Deliberately omits correct answers,
    explanations and `is_correct` flags while the attempt is in progress.
    """
    items = []
    for number, tq in enumerate(test_questions, start=1):
        q = tq.question
        answer = answers.get(tq.id)
        items.append({
            "id": tq.id,
            "number": number,
            "text": q.text,
            "image": q.image.url if q.image else None,
            "type": q.question_type,
            "marks": float(tq.effective_marks),
            "negative_marks": float(tq.effective_negative_marks),
            "subject": q.subject.name,
            "chapter": q.chapter.name if q.chapter else "",
            "options": [{"id": o.id, "text": o.text} for o in q.options.all()],
            "state": {
                "selected": [o.id for o in answer.selected_options.all()] if answer else [],
                "text": answer.text_answer if answer else "",
                "marked": answer.is_marked_for_review if answer else False,
                "visited": answer.visited if answer else False,
            },
        })
    return items


class SaveAnswerSerializer(serializers.Serializer):
    test_question = serializers.IntegerField()
    options = serializers.ListField(child=serializers.IntegerField(), required=False,
                                    allow_empty=True, max_length=10)
    text_answer = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    marked_for_review = serializers.BooleanField(required=False, allow_null=True, default=None)
    time_spent = serializers.IntegerField(required=False, min_value=0, max_value=3600, default=0)
