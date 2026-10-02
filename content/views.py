from django.db.models import F, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from analytics.models import UserActivity
from analytics.services import log_activity
from boards.models import Topic
from core.files import serve_file
from core.filters import apply_hierarchy_filters, paginate, to_int

from .models import StudyMaterial


def material_list(request):
    qs = StudyMaterial.objects.published().select_related("subject__class_level__board", "chapter")
    qs, filter_ctx = apply_hierarchy_filters(request, qs)
    material_type = request.GET.get("type")
    topic_id = to_int(request.GET.get("topic"))
    q = request.GET.get("q", "").strip()
    if material_type in StudyMaterial.MaterialType.values:
        qs = qs.filter(material_type=material_type)
    if topic_id:
        qs = qs.filter(topic_id=topic_id)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q))
    chapter_id = filter_ctx["selected"]["chapter"]
    return render(request, "content/material_list.html", {
        **filter_ctx,
        "page_obj": paginate(request, qs.order_by("-is_featured", "-created_at"), 12),
        "material_types": StudyMaterial.MaterialType.choices,
        "selected_type": material_type,
        "topics": Topic.objects.published().filter(chapter_id=chapter_id) if chapter_id else [],
        "selected_topic": topic_id,
        "q": q,
    })


def material_detail(request, slug):
    material = get_object_or_404(
        StudyMaterial.objects.published().select_related("subject__class_level__board", "chapter",
                                                         "topic"),
        slug=slug)
    StudyMaterial.objects.filter(pk=material.pk).update(view_count=F("view_count") + 1)
    log_activity(request.user, UserActivity.Type.VIEW_MATERIAL, f"Read {material.title}", obj=material)
    related = StudyMaterial.objects.published().filter(
        Q(chapter=material.chapter) if material.chapter_id else Q(subject=material.subject)
    ).exclude(pk=material.pk)[:4]
    return render(request, "content/material_detail.html",
                  {"material": material, "related": related})


@xframe_options_sameorigin
def material_file(request, slug):
    material = get_object_or_404(StudyMaterial.objects.published(), slug=slug)
    as_attachment = request.GET.get("download") == "1"
    if as_attachment:
        StudyMaterial.objects.filter(pk=material.pk).update(download_count=F("download_count") + 1)
    return serve_file(material.file, material.title, as_attachment=as_attachment)
