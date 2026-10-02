from core.viewsets import PublishedContentViewSet

from .models import Board, Chapter, ClassLevel, Subject, Topic
from .serializers import (BoardSerializer, ChapterSerializer, ClassLevelSerializer,
                          SubjectSerializer, TopicSerializer)


class BoardViewSet(PublishedContentViewSet):
    queryset = Board.objects.all()
    serializer_class = BoardSerializer
    filterset_fields = ["board_type", "is_featured", "slug"]
    search_fields = ["name", "short_name", "state"]
    pagination_class = None


class ClassLevelViewSet(PublishedContentViewSet):
    queryset = ClassLevel.objects.select_related("board")
    serializer_class = ClassLevelSerializer
    filterset_fields = ["board", "board__slug", "number"]
    search_fields = ["name"]
    pagination_class = None


class SubjectViewSet(PublishedContentViewSet):
    queryset = Subject.objects.select_related("class_level__board")
    serializer_class = SubjectSerializer
    filterset_fields = ["class_level", "class_level__board", "is_popular"]
    search_fields = ["name", "code"]
    pagination_class = None


class ChapterViewSet(PublishedContentViewSet):
    queryset = Chapter.objects.select_related("subject")
    serializer_class = ChapterSerializer
    filterset_fields = ["subject", "subject__class_level"]
    search_fields = ["name"]
    pagination_class = None


class TopicViewSet(PublishedContentViewSet):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    filterset_fields = ["chapter"]
    search_fields = ["name"]
