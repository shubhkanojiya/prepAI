"""Small shared helpers."""
import hashlib
import html
import re

from django.utils.safestring import mark_safe
from django.utils.text import slugify

_WS_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]")


def normalize_text(text):
    """Lower-case, strip punctuation and collapse whitespace (for matching)."""
    text = re.sub(r"['’`]", "", (text or "").lower())  # "Newton's" == "newtons"
    text = _NON_WORD_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def text_fingerprint(text):
    """Stable hash of normalized text — used to detect repeated questions."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def unique_slug(model, value, slug_field="slug", queryset=None, max_length=200):
    """Return a slug for `value` that is unique within `queryset`."""
    base = slugify(value)[: max_length - 10] or "item"
    queryset = queryset if queryset is not None else model._default_manager.all()
    slug, counter = base, 2
    while queryset.filter(**{slug_field: slug}).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


# ---------------------------------------------------------------------------
# Minimal, safe Markdown renderer (content is HTML-escaped first).
# Supports headings, lists, fenced code, bold, italic and inline code — enough
# for study notes and AI answers without pulling in a sanitiser dependency.
# ---------------------------------------------------------------------------
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])")
_CODE = re.compile(r"`([^`]+)`")


def _inline(text):
    text = _CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    return _ITALIC.sub(r"<em>\1</em>", text)


def render_markdown(source):
    if not source:
        return ""
    lines = html.escape(source).replace("\r\n", "\n").split("\n")
    out, paragraph, list_type, in_code = [], [], None, False

    def flush_paragraph():
        if paragraph:
            out.append("<p>" + _inline("<br>".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list():
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(line + "\n")
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)) + 2, 6)  # render #  as h3 inside pages
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif bullet or numbered:
            flush_paragraph()
            wanted = "ul" if bullet else "ol"
            if list_type != wanted:
                close_list()
                out.append(f"<{wanted}>")
                list_type = wanted
            out.append("<li>" + _inline((bullet or numbered).group(1)) + "</li>")
        elif not stripped:
            flush_paragraph()
            close_list()
        else:
            close_list()
            paragraph.append(stripped)
    flush_paragraph()
    close_list()
    if in_code:
        out.append("</code></pre>")
    return mark_safe("\n".join(out))
