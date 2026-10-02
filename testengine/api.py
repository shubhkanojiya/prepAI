from django.db.models import Count, Q
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .models import Test, TestAttempt
from .serializers import (AttemptSerializer, SaveAnswerSerializer, TestSerializer,
                          attempt_question_payload)


class TestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TestSerializer
    lookup_field = "slug"
    filterset_fields = ["test_type", "difficulty", "board", "class_level", "subject", "chapter"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        return (Test.objects.published().select_related("subject")
                .annotate(question_count=Count("test_questions",
                                               filter=Q(test_questions__question__is_published=True)))
                .order_by("-is_featured", "-created_at"))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def start(self, request, slug=None):
        try:
            attempt = services.start_attempt(request.user, self.get_object())
        except services.TestEngineError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(AttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class TestAttemptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    serializer_class = AttemptSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "test"]

    def get_queryset(self):
        return TestAttempt.objects.filter(user=self.request.user).select_related("test")

    def get_object(self):
        return services.expire_if_needed(super().get_object())

    @action(detail=True, methods=["get"])
    def questions(self, request, pk=None):
        attempt = self.get_object()
        answers = {a.test_question_id: a for a in attempt.answers.prefetch_related("selected_options")}
        return Response({
            "attempt": AttemptSerializer(attempt).data,
            "questions": attempt_question_payload(attempt, services.ordered_test_questions(attempt),
                                                  answers),
        })

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        attempt = self.get_object()
        payload = SaveAnswerSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            services.save_answer(
                attempt, data["test_question"],
                option_ids=data.get("options"),
                text_answer=data.get("text_answer"),
                marked_for_review=data.get("marked_for_review"),
                time_spent_seconds=data.get("time_spent", 0),
            )
        except services.TestEngineError as exc:
            attempt.refresh_from_db()
            return Response({"error": {"message": str(exc), "code": "test_closed"
                                       if not attempt.is_in_progress else "invalid"},
                             "result_url": attempt.get_absolute_url()},
                            status=status.HTTP_409_CONFLICT if not attempt.is_in_progress
                            else status.HTTP_400_BAD_REQUEST)
        return Response({"saved": True, "remaining_seconds": attempt.remaining_seconds})

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        attempt = services.submit_attempt(self.get_object(),
                                          auto=bool(request.data.get("auto")))
        return Response(AttemptSerializer(attempt).data)

    @action(detail=True, methods=["get"])
    def result(self, request, pk=None):
        attempt = self.get_object()
        if attempt.is_in_progress:
            raise ValidationError({"detail": "Submit the test to see results."})
        result = services.build_result(attempt)
        return Response({
            "attempt": AttemptSerializer(attempt).data,
            "subject_breakdown": result["subject_breakdown"],
            "chapter_breakdown": result["chapter_breakdown"],
            "questions": [
                {"number": r["number"], "state": r["state"], "question": r["question"].text,
                 "selected": sorted(r["selected"]),
                 "correct_options": [o.id for o in r["question"].options.all() if o.is_correct],
                 "your_answer": r["answer"].text_answer if r["answer"] else "",
                 "model_answer": r["question"].answer,
                 "explanation": r["question"].explanation if attempt.test.show_explanations else "",
                 "marks_awarded": str(r["answer"].marks_awarded) if r["answer"] else "0"}
                for r in result["questions"]
            ],
        })
