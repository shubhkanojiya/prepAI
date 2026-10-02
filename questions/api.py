from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import PublishedContentViewSet

from .models import Question
from .serializers import (FrequencySerializer, PredictRequestSerializer, QuestionSerializer,
                          prediction_payload)
from .services.frequency import analyze_question
from .services.predictor import predict


class QuestionViewSet(PublishedContentViewSet):
    queryset = (Question.objects.select_related("subject", "chapter", "topic")
                .prefetch_related("options", "concepts"))
    serializer_class = QuestionSerializer
    filterset_fields = ["subject", "chapter", "topic", "question_type", "difficulty",
                        "is_important", "subject__class_level", "subject__class_level__board"]
    search_fields = ["text", "concepts__name"]
    ordering_fields = ["created_at", "difficulty", "marks"]

    @action(detail=True, methods=["get"])
    def frequency(self, request, pk=None):
        """Historical frequency analysis computed from stored papers."""
        return Response(FrequencySerializer(analyze_question(self.get_object())).data)

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def predict(self, request):
        """
        Exam Question Predictor. Body: {"text": "...", "board"?, "class_level"?, "subject"?}.
        Returns past appearances (count, years, papers) and a history-based
        likelihood estimate for the upcoming exam.
        """
        payload = PredictRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        report = predict(data["text"], board=data.get("board"), class_level=data.get("class_level"),
                         subject=data.get("subject"))
        return Response(prediction_payload(report))
