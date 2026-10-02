"""
AI question scanner pipeline:

  image/text → validate → (optional OCR) → vision model → detected question,
  subject/chapter → answer → steps → concept → follow-up questions → history.
"""
import io
import logging
import time

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from boards.models import Chapter, Subject
from core.validators import IMAGE_MIME_TYPES, validate_image_file
from services import ai_service, ocr_service

from .models import ScannerHistory

logger = logging.getLogger("prepai.scanner")

MAX_EDGE_PX = 1568  # larger images cost more and don't improve reading accuracy

SCAN_SCHEMA = {
    "type": "object",
    "properties": {
        "is_question_found": {"type": "boolean"},
        "extracted_text": {"type": "string"},
        "question": {"type": "string"},
        "is_handwritten": {"type": "boolean"},
        "subject": {"type": "string"},
        "chapter": {"type": "string"},
        "topic": {"type": "string"},
        "answer": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "concept": {"type": "string"},
        "follow_up_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_question_found", "extracted_text", "question", "is_handwritten", "subject",
                 "chapter", "topic", "answer", "steps", "concept", "follow_up_questions"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are PrepAI's question scanner for Indian school students preparing for \
board examinations (CBSE, ICSE and state boards).

You receive a photo or scan of a question (printed or handwritten), or typed text. Your job:
1. Transcribe all readable text exactly into `extracted_text`.
2. Identify the single main question into `question`. If the image contains no question \
(or is unreadable), set `is_question_found` to false and leave the other text fields empty.
3. Name the school subject (e.g. Mathematics, Physics, Chemistry, Biology, English, \
Accountancy, Economics, Computer Science), and the likely chapter and topic as they are \
usually named in Indian board syllabi. Use an empty string when unsure.
4. Give the final `answer` concisely.
5. Give a numbered-style list of `steps` a student can follow, each step one short paragraph. \
Show working for numerical problems. Write mathematics with LaTeX between $...$.
6. Explain the underlying `concept` in simple language, in 3-6 sentences.
7. Suggest 3 `follow_up_questions` of similar difficulty for practice.

Be accurate; if a question is ambiguous, state the assumption you made in the first step."""


def _prepare_image(uploaded_file):
    """Validate, fix orientation, downscale; return (jpeg_bytes, media_type)."""
    image_format = validate_image_file(uploaded_file)
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            if max(img.size) > MAX_EDGE_PX or image_format not in ("JPEG", "PNG"):
                img.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
                buffer = io.BytesIO()
                img.convert("RGB").save(buffer, "JPEG", quality=88)
                return buffer.getvalue(), "image/jpeg"
    except OSError:
        logger.warning("Could not re-encode image; sending original")
    return raw, IMAGE_MIME_TYPES[image_format]


def _student_context(user):
    profile = getattr(user, "profile", None) if user and user.is_authenticated else None
    if profile and profile.class_level_id:
        return f"The student studies {profile.class_level.name} under {profile.class_level.board.name}."
    if profile and profile.board_id:
        return f"The student studies under {profile.board.name}."
    return ""


def _match_subject(user, subject_name, chapter_name):
    if not subject_name:
        return None, None
    subjects = Subject.objects.published().filter(name__iexact=subject_name)
    profile = getattr(user, "profile", None) if user and user.is_authenticated else None
    subject = None
    if profile and profile.class_level_id:
        subject = subjects.filter(class_level_id=profile.class_level_id).first()
    if subject is None and profile and profile.board_id:
        subject = subjects.filter(class_level__board_id=profile.board_id).first()
    if subject is None:
        return None, None
    chapter = None
    if chapter_name:
        chapter = (Chapter.objects.published().filter(subject=subject, name__iexact=chapter_name).first()
                   or Chapter.objects.published().filter(subject=subject,
                                                        name__icontains=chapter_name).first())
    return subject, chapter


def scan(user, image_file=None, typed_question=""):
    """
    Run the scanner. Returns a ScannerHistory (saved for logged-in users,
    unsaved for guests). Raises AIServiceError when the AI is unavailable
    (the failed attempt is still recorded for logged-in users).
    """
    started = time.monotonic()
    typed_question = (typed_question or "").strip()[:4000]
    is_member = bool(user and user.is_authenticated)  # guests' scans are never stored
    record = ScannerHistory(user=user if is_member else None, typed_question=typed_question)

    content = []
    if image_file is not None:
        image_bytes, media_type = _prepare_image(image_file)
        content.append(ai_service.image_block(image_bytes, media_type))
        ocr = ocr_service.extract_text(image_bytes)
        if ocr:
            content.append(ai_service.text_block(
                f"OCR pre-extraction (may contain errors):\n{ocr.text[:4000]}"))
        if is_member:
            record.image.save(f"scan.{'jpg' if media_type == 'image/jpeg' else 'png'}",
                              ContentFile(image_bytes), save=False)
    if typed_question:
        content.append(ai_service.text_block(f"Typed question:\n{typed_question}"))
    if not content:
        raise ValueError("Provide an image or a typed question.")
    context = _student_context(user)
    content.append(ai_service.text_block(
        (context + " " if context else "") + "Analyse and solve the question."))

    try:
        data = ai_service.generate_json(SYSTEM_PROMPT, content, SCAN_SCHEMA)
    except ai_service.AIServiceError as exc:
        record.status = ScannerHistory.Status.FAILED
        record.error_message = exc.user_message[:300]
        record.processing_ms = int((time.monotonic() - started) * 1000)
        if is_member:
            record.save()
        raise

    record.processing_ms = int((time.monotonic() - started) * 1000)
    record.extracted_text = data.get("extracted_text", "")
    if not data.get("is_question_found"):
        record.status = ScannerHistory.Status.FAILED
        record.error_message = ("We couldn't find a question in this image. "
                                "Try a clearer, well-lit photo with the question in focus.")
    else:
        record.status = ScannerHistory.Status.COMPLETED
        record.detected_question = data.get("question", "")
        record.detected_subject_name = data.get("subject", "")[:120]
        record.detected_topic_name = (data.get("topic") or data.get("chapter") or "")[:200]
        record.is_handwritten = bool(data.get("is_handwritten"))
        record.answer = data.get("answer", "")
        record.steps = [s for s in data.get("steps", []) if s][:20]
        record.concept = data.get("concept", "")
        record.follow_up_questions = [q for q in data.get("follow_up_questions", []) if q][:5]
        record.subject, record.chapter = _match_subject(user, record.detected_subject_name,
                                                        data.get("chapter", ""))
    if is_member:
        record.save()
        from analytics.models import UserActivity
        from analytics.services import log_activity

        log_activity(user, UserActivity.Type.SCAN, "Scanned a question", obj=record)
    return record
