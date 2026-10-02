from django import template
from django.utils.http import urlencode

from core.utils import render_markdown

register = template.Library()


@register.filter(name="markdown")
def markdown_filter(value):
    return render_markdown(value)


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Return the current query string with the given params replaced (empty = removed)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return "?" + params.urlencode() if params else "?"


@register.simple_tag
def query_string(**kwargs):
    return urlencode({k: v for k, v in kwargs.items() if v not in (None, "")})


@register.inclusion_tag("components/bookmark_button.html", takes_context=True)
def bookmark_button(context, obj, size="", label=True):
    from bookmarks.services import bookmarked_ids, kind_for_object

    request = context["request"]
    return {
        "request": request,
        "kind": kind_for_object(obj),
        "object_id": obj.pk,
        "is_bookmarked": obj.pk in bookmarked_ids(request, type(obj)),
        "size": size,
        "show_label": label,
        "user": request.user,
    }


@register.filter
def duration(seconds):
    """Format seconds as 'Xh Ym' / 'Ym Zs'."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "—"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


@register.filter
def filesize(num_bytes):
    try:
        num = float(num_bytes)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


@register.filter
def score_tone(percentage):
    """Map a percentage to a semantic tone used by CSS (good / warn / bad)."""
    try:
        value = float(percentage)
    except (TypeError, ValueError):
        return "muted"
    if value >= 75:
        return "good"
    if value >= 50:
        return "warn"
    return "bad"


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
