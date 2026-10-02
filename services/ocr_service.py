"""
OCR abstraction for the AI question scanner.

OCR_BACKEND:
* ``vision_llm`` (default) — no separate OCR step; the multimodal AI model
  reads the image directly (best for handwriting and diagrams).
* ``tesseract`` — run Tesseract first (requires `pytesseract` + the binary);
  the extracted text is passed to the AI as a hint alongside the image.
* ``none`` — skip OCR entirely.
"""
import io
import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger("prepai.ocr")


@dataclass
class OCRResult:
    text: str
    backend: str


def extract_text(image_bytes: bytes) -> OCRResult | None:
    """Return pre-extracted text, or None when the AI model should read the image itself."""
    backend = (settings.OCR_BACKEND or "vision_llm").lower()
    if backend != "tesseract":
        return None
    try:
        import pytesseract
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            text = pytesseract.image_to_string(img.convert("L"))
        text = text.strip()
        return OCRResult(text=text, backend="tesseract") if text else None
    except Exception:  # OCR is best-effort; the vision model is the fallback.
        logger.exception("Tesseract OCR failed; falling back to vision model")
        return None
