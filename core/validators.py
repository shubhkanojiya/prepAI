"""Upload validators for PDFs and images.

Validation checks extension, size AND file content (magic bytes / Pillow
decoding), so a renamed executable cannot be uploaded as a "PDF".
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
IMAGE_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


def _read_head(file_obj, size=1024):
    position = file_obj.tell() if hasattr(file_obj, "tell") else 0
    file_obj.seek(0)
    head = file_obj.read(size)
    file_obj.seek(position)
    return head


@deconstructible
class PDFValidator:
    """Validates that an uploaded file is a real PDF within the size limit."""

    def __call__(self, file_obj):
        name = getattr(file_obj, "name", "") or ""
        if not name.lower().endswith(".pdf"):
            raise ValidationError("Only PDF files are allowed.")
        max_bytes = settings.MAX_PDF_UPLOAD_MB * 1024 * 1024
        if file_obj.size > max_bytes:
            raise ValidationError(f"PDF is too large. Maximum size is {settings.MAX_PDF_UPLOAD_MB} MB.")
        if not _read_head(file_obj, 5).startswith(b"%PDF-"):
            raise ValidationError("The uploaded file is not a valid PDF document.")

    def __eq__(self, other):
        return isinstance(other, PDFValidator)


@deconstructible
class ImageValidator:
    """Validates that an uploaded file is a decodable image within the size limit."""

    def __call__(self, file_obj):
        validate_image_file(file_obj)

    def __eq__(self, other):
        return isinstance(other, ImageValidator)


MAX_IMAGE_PIXELS = 64_000_000  # fits 50 MP phone photos; blocks decompression bombs


def validate_image_file(file_obj):
    """Validate and return the detected Pillow format (e.g. 'JPEG')."""
    from PIL import Image, UnidentifiedImageError

    max_bytes = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
    if file_obj.size > max_bytes:
        raise ValidationError(
            f"Image is too large. Maximum size is {settings.MAX_IMAGE_UPLOAD_MB} MB."
        )
    try:
        file_obj.seek(0)
        with Image.open(file_obj) as img:
            img.verify()
            image_format = img.format
            width, height = img.size
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise ValidationError("The uploaded file is not a valid image.")
    finally:
        file_obj.seek(0)
    # A small file can still decode to a huge bitmap and exhaust server memory.
    if width * height > MAX_IMAGE_PIXELS:
        raise ValidationError("Image dimensions are too large. Please upload a smaller photo.")
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Unsupported image format. Use JPG, PNG, WEBP or GIF.")
    return image_format


validate_pdf = PDFValidator()
validate_image = ImageValidator()
