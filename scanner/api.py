from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core.viewsets import ScopedThrottleMixin

from . import services
from .models import ScannerHistory


class ScannerHistorySerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)
    chapter_name = serializers.CharField(source="chapter.name", read_only=True, default=None)
    subject_url = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = ScannerHistory
        fields = ["id", "status", "image", "typed_question", "extracted_text",
                  "detected_question", "detected_subject_name", "detected_topic_name",
                  "subject", "subject_name", "subject_url", "chapter", "chapter_name",
                  "is_handwritten", "answer", "steps", "concept", "follow_up_questions",
                  "error_message", "processing_ms", "created_at", "url"]
        read_only_fields = fields

    def get_subject_url(self, obj):
        target = obj.chapter or obj.subject
        return target.get_absolute_url() if target else None

    def get_url(self, obj):
        return obj.get_absolute_url() if obj.pk else None


class ScanRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False)
    question = serializers.CharField(required=False, allow_blank=True, max_length=4000)

    def validate(self, attrs):
        if not attrs.get("image") and not (attrs.get("question") or "").strip():
            raise serializers.ValidationError("Upload an image or type a question.")
        return attrs


class ScannerViewSet(ScopedThrottleMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """POST an image (multipart) or typed question to scan; GET your scan history."""

    serializer_class = ScannerHistorySerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    action_throttle_scopes = {"create": "ai_scanner"}

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]  # guests may scan; history is kept for users only
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return ScannerHistory.objects.filter(user=self.request.user).select_related("subject",
                                                                                    "chapter")

    def create(self, request, *args, **kwargs):
        payload = ScanRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            record = services.scan(request.user, payload.validated_data.get("image"),
                                   payload.validated_data.get("question", ""))
        except DjangoValidationError as exc:
            raise ValidationError({"image": exc.messages})
        return Response(ScannerHistorySerializer(record, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)
