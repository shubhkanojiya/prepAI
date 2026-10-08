from rest_framework import mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Recommendation
from .services import get_for_user


class RecommendationSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Recommendation
        fields = ["id", "rec_type", "reason", "score", "title", "url", "created_at"]

    def get_title(self, obj):
        target = obj.content_object
        return getattr(target, "title", None) or getattr(target, "name", None) or str(target)

    def get_url(self, obj):
        target = obj.content_object
        return target.get_absolute_url() if target is not None else None


class RecommendationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = RecommendationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Recommendation.objects.filter(user=self.request.user, is_dismissed=False)

    def list(self, request, *args, **kwargs):
        recs = get_for_user(request.user, limit=12)
        return Response(self.get_serializer(recs, many=True).data)

    @action(detail=True, methods=["post"])
    def dismiss(self, request, pk=None):
        rec = self.get_object()
        rec.is_dismissed = True
        rec.save(update_fields=["is_dismissed", "updated_at"])
        return Response({"dismissed": True})
