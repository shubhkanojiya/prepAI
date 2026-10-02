from core.viewsets import PublishedContentViewSet

from .models import StudyMaterial
from .serializers import StudyMaterialSerializer


class StudyMaterialViewSet(PublishedContentViewSet):
    queryset = StudyMaterial.objects.select_related("subject", "chapter")
    serializer_class = StudyMaterialSerializer
    lookup_field = "slug"
    filterset_fields = ["subject", "chapter", "topic", "material_type", "is_featured",
                        "subject__class_level", "subject__class_level__board"]
    search_fields = ["title", "summary", "body"]
    ordering_fields = ["created_at", "view_count"]
