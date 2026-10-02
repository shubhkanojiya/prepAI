from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import PublishedContentViewSet
from questions.serializers import QuestionSerializer
from questions.services.frequency import important_questions_for_paper

from .models import PreviousYearPaper, QuestionPaper
from .serializers import QuestionPaperSerializer

FILTER_FIELDS = {
    "subject": ["exact"],
    "chapter": ["exact"],
    "subject__class_level": ["exact"],
    "subject__class_level__board": ["exact"],
    "paper_type": ["exact"],
    "exam_type": ["exact"],
    "difficulty": ["exact"],
    "year": ["exact", "gte", "lte"],
}


class QuestionPaperViewSet(PublishedContentViewSet):
    queryset = QuestionPaper.objects.select_related("subject__class_level__board")
    serializer_class = QuestionPaperSerializer
    lookup_field = "slug"
    filterset_fields = FILTER_FIELDS
    search_fields = ["title", "description", "subject__name"]
    ordering_fields = ["year", "created_at", "download_count"]

    @action(detail=True, methods=["get"], url_path="important-questions")
    def important_questions(self, request, slug=None):
        questions = important_questions_for_paper(self.get_object())
        return Response(QuestionSerializer(questions, many=True, context={"request": request}).data)


class PreviousYearPaperViewSet(QuestionPaperViewSet):
    queryset = PreviousYearPaper.objects.select_related("subject__class_level__board")
