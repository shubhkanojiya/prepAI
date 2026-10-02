from rest_framework import mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .models import Bookmark


class BookmarkSerializer(serializers.ModelSerializer):
    kind = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Bookmark
        fields = ["id", "kind", "object_id", "title", "url", "note", "created_at"]

    def get_kind(self, obj):
        return services.kind_for_object(obj.content_object) if obj.content_object else None

    def get_title(self, obj):
        target = obj.content_object
        return (getattr(target, "title", None) or str(target)) if target else "(removed)"

    def get_url(self, obj):
        target = obj.content_object
        return target.get_absolute_url() if target is not None else None


class ToggleSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=list(services.KINDS))
    object_id = serializers.IntegerField(min_value=1)


class BookmarkViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = (Bookmark.objects.filter(user=self.request.user)
              .select_related("content_type").prefetch_related("content_object"))
        kind = self.request.query_params.get("kind")
        if kind in services.KINDS:
            qs = qs.filter(content_type=services.content_type_for_kind(kind))
        return qs

    @action(detail=False, methods=["post"])
    def toggle(self, request):
        payload = ToggleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            bookmarked = services.toggle(request.user, payload.validated_data["kind"],
                                         payload.validated_data["object_id"])
        except services.BookmarkError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response({"bookmarked": bookmarked})
