"""AI Study Assistant: builds prompts, keeps history, calls the AI service layer."""
from django.db import transaction

from services import ai_service

from .models import AIConversation, AIMessage

HISTORY_LIMIT = 20  # most recent messages sent as context

BASE_SYSTEM_PROMPT = """You are PrepAI, a friendly and accurate AI study assistant for Indian \
school students preparing for board examinations (CBSE, ICSE and state boards).

How to help:
- Teach, don't just answer. Explain reasoning step by step and check understanding.
- Match the student's class level and board syllabus; use terminology from standard Indian \
textbooks (e.g. NCERT for CBSE) where relevant.
- For numericals show every step and the formula used. Write mathematics in LaTeX between \
$...$ (inline) or $$...$$ (display).
- Use short paragraphs, headings and bullet lists in Markdown.
- When creating practice questions or quizzes, number them and give answers at the end \
under a heading "Answers" so the student can self-check.
- If you are unsure or the question is outside the syllabus, say so honestly.
- Never claim to know which questions will appear in an upcoming examination. You may \
discuss historical trends in general terms, noting that they do not guarantee future questions.
- Stay focused on studies; politely redirect unrelated or unsafe requests."""

MODE_INSTRUCTIONS = {
    AIConversation.Mode.GENERAL: "",
    AIConversation.Mode.SIMPLE: "Explain in very simple language with an everyday example. "
                                "Keep it short (under 200 words) unless asked for more.",
    AIConversation.Mode.DETAILED: "Give a thorough, well-structured explanation with "
                                  "definitions, derivations or examples where useful.",
    AIConversation.Mode.PRACTICE: "Focus on generating practice questions of mixed difficulty "
                                  "in board-exam style, with answers at the end.",
    AIConversation.Mode.QUIZ: "Act as a quiz master: ask multiple-choice questions and, when "
                              "the student answers, say whether it is right and explain why.",
    AIConversation.Mode.REVISION: "Help the student revise: summarise key points, formulas, "
                                  "definitions and commonly tested concepts concisely.",
}

STARTER_PROMPTS = [
    "What is photosynthesis?",
    "Explain Newton's laws of motion in simple language",
    "Give me 10 questions on algebra",
    "Create a 5-question quiz on chemical reactions",
    "Help me revise the chapter on electricity",
    "What are the important concepts in trigonometry?",
]


def build_system_prompt(conversation):
    parts = [BASE_SYSTEM_PROMPT]
    profile = getattr(conversation.user, "profile", None)
    student = []
    if profile and profile.class_level_id:
        student.append(f"The student studies {profile.class_level.name} under "
                       f"{profile.class_level.board.name}.")
    elif profile and profile.board_id:
        student.append(f"The student studies under {profile.board.name}.")
    if profile and profile.explanation_style == "simple":
        student.append("They prefer simple, short explanations.")
    if profile and profile.preferred_language and profile.preferred_language != "en":
        student.append(f"Reply in {profile.get_preferred_language_display()} if they write in it; "
                       "otherwise use English.")
    if conversation.subject_id:
        student.append(f"This conversation is about {conversation.subject.name}.")
    if student:
        parts.append("Student context: " + " ".join(student))
    mode_text = MODE_INSTRUCTIONS.get(conversation.mode)
    if mode_text:
        parts.append(f"Mode — {conversation.get_mode_display()}: {mode_text}")
    return "\n\n".join(parts)


def _title_from(text):
    title = " ".join(text.split())[:60]
    return title + ("…" if len(text) > 60 else "")


def send_message(conversation, text):
    """
    Store the student's message, get the AI reply and store it.
    On AI failure the student's message is rolled back (so a retry doesn't
    duplicate it) and AIServiceError propagates to the caller.
    """
    text = text.strip()
    # The (slow) AI call deliberately runs outside a DB transaction.
    user_message = AIMessage.objects.create(conversation=conversation,
                                            role=AIMessage.Role.USER, content=text)
    history = list(conversation.messages.order_by("-created_at", "-id")[:HISTORY_LIMIT])[::-1]
    # The API requires the first message to be from the user.
    while history and history[0].role != AIMessage.Role.USER:
        history.pop(0)
    messages = [{"role": m.role, "content": m.content} for m in history]
    try:
        response = ai_service.chat(build_system_prompt(conversation), messages)
    except ai_service.AIServiceError:
        user_message.delete()
        raise
    with transaction.atomic():
        reply = AIMessage.objects.create(
            conversation=conversation, role=AIMessage.Role.ASSISTANT, content=response.text,
            model_name=response.model[:60], input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        if conversation.title == "New conversation":
            conversation.title = _title_from(text)
        conversation.save(update_fields=["title", "updated_at"])

    from analytics.models import UserActivity
    from analytics.services import log_activity

    log_activity(conversation.user, UserActivity.Type.ASK_AI, _title_from(text),
                 url=f"/assistant/{conversation.pk}/")
    return user_message, reply
