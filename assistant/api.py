from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import ScopedThrottleMixin

from . import services
from .models import AIConversation, AIMessage


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ["id", "role", "content", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIConversation
        fields = ["id", "title", "mode", "subject", "is_archived", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class ConversationDetailSerializer(ConversationSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ["messages"]


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=6000, trim_whitespace=True)


class ConversationViewSet(ScopedThrottleMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    action_throttle_scopes = {"messages": "ai_assistant"}

    def get_queryset(self):
        return AIConversation.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return ConversationDetailSerializer if self.action == "retrieve" else ConversationSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def messages(self, request, pk=None):
        """Send a message; returns the stored student message and the AI reply."""
        conversation = self.get_object()
        payload = SendMessageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        user_message, reply = services.send_message(conversation, payload.validated_data["content"])
        conversation.refresh_from_db(fields=["title"])
        return Response({
            "conversation": ConversationSerializer(conversation).data,
            "user_message": AIMessageSerializer(user_message).data,
            "reply": AIMessageSerializer(reply).data,
        }, status=status.HTTP_201_CREATED)
