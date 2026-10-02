from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from boards.models import Subject
from services.ai_service import is_configured

from .models import AIConversation
from .services import STARTER_PROMPTS


def _subjects_for(user):
    profile = user.profile
    subjects = Subject.objects.published()
    if profile.class_level_id:
        return subjects.filter(class_level_id=profile.class_level_id)
    if profile.board_id:
        return subjects.filter(class_level__board_id=profile.board_id)
    return subjects.select_related("class_level")[:50]


@login_required
def assistant_page(request, pk=None):
    conversations = AIConversation.objects.filter(user=request.user, is_archived=False)[:30]
    conversation = None
    if pk is not None:
        conversation = get_object_or_404(AIConversation, pk=pk, user=request.user)
    return render(request, "assistant/assistant.html", {
        "conversations": conversations,
        "conversation": conversation,
        "chat_messages": conversation.messages.all() if conversation else [],
        "modes": AIConversation.Mode.choices,
        "subjects": _subjects_for(request.user),
        "starter_prompts": STARTER_PROMPTS,
        "ai_enabled": is_configured(),
        "prefill": request.GET.get("q", "")[:1000],
    })


@login_required
@require_POST
def delete_conversation(request, pk):
    conversation = get_object_or_404(AIConversation, pk=pk, user=request.user)
    conversation.delete()
    messages.success(request, "Conversation deleted.")
    return redirect("assistant:home")
